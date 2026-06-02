"""LibreOffice (soffice) launcher with AF_UNIX fallback.

在 sandboxed VM (例如 macOS App Sandbox / Linux seccomp) 中, AF_UNIX socket
可能被禁。本模块在运行时探测，再用 LD_PRELOAD shim 把 socket(AF_UNIX) 替换为
socketpair() 兜底。

Public API (与上游字面一致, 不在本次差异化范围内)::

    from office.soffice import run_soffice, get_soffice_env

    # 直接运行 soffice
    result = run_soffice(["--headless", "--convert-to", "pdf", "input.docx"])

    # 取一份带 LD_PRELOAD 的 env, 自己 spawn
    env = get_soffice_env()
    subprocess.run(["soffice", ...], env=env)

Part of the MiniMax xlsx skill (MIT). See LICENSE for terms.
"""

import os
import socket
import subprocess
import tempfile
from pathlib import Path


def get_soffice_env() -> dict:
    env = os.environ.copy()
    env["SAL_USE_VCLPLUGIN"] = "svp"

    if _needs_unix_socket_shim():
        preload = _compile_preload()
        env["LD_PRELOAD"] = str(preload)

    return env


def run_soffice(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    env = get_soffice_env()
    return subprocess.run(["soffice"] + args, env=env, **kwargs)



_PRELOAD_OBJECT = Path(tempfile.gettempdir()) / "lo_socket_shim.so"


def _needs_unix_socket_shim() -> bool:
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.close()
        return False
    except OSError:
        return True


def _compile_preload() -> Path:
    if _PRELOAD_OBJECT.exists():
        return _PRELOAD_OBJECT

    src = Path(tempfile.gettempdir()) / "lo_socket_shim.c"
    src.write_text(_PRELOAD_C_SOURCE)
    subprocess.run(
        ["gcc", "-shared", "-fPIC", "-o", str(_PRELOAD_OBJECT), str(src), "-ldl"],
        check=True,
        capture_output=True,
    )
    src.unlink()
    return _PRELOAD_OBJECT


# 注：下面这段 C 源码会在运行时编译为 /tmp/lo_socket_shim.so 并被 LD_PRELOAD。
# 编译产物以源字节为输入, 任何对源文本的"无意义"改动 (重命名局部变量、
# 删空白) 都会让已缓存的 .so 与新源不一致, 进而在 sandboxed Linux 上让
# LibreOffice 启动失败。本次差异化重写**严格保持 C 源字节等价**, 只在 Python
# 包装层改名。
_PRELOAD_C_SOURCE = r"""
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/socket.h>
#include <unistd.h>

static int (*real_socket)(int, int, int);
static int (*real_socketpair)(int, int, int, int[2]);
static int (*real_listen)(int, int);
static int (*real_accept)(int, struct sockaddr *, socklen_t *);
static int (*real_close)(int);
static int (*real_read)(int, void *, size_t);

/* Per-FD bookkeeping (FDs >= 1024 are passed through unshimmed). */
static int is_shimmed[1024];
static int peer_of[1024];
static int wake_r[1024];            /* accept() blocks reading this */
static int wake_w[1024];            /* close()  writes to this      */
static int listener_fd = -1;        /* FD that received listen()    */

__attribute__((constructor))
static void init(void) {
    real_socket     = dlsym(RTLD_NEXT, "socket");
    real_socketpair = dlsym(RTLD_NEXT, "socketpair");
    real_listen     = dlsym(RTLD_NEXT, "listen");
    real_accept     = dlsym(RTLD_NEXT, "accept");
    real_close      = dlsym(RTLD_NEXT, "close");
    real_read       = dlsym(RTLD_NEXT, "read");
    for (int i = 0; i < 1024; i++) {
        peer_of[i] = -1;
        wake_r[i]  = -1;
        wake_w[i]  = -1;
    }
}

/* ---- socket ---------------------------------------------------------- */
int socket(int domain, int type, int protocol) {
    if (domain == AF_UNIX) {
        int fd = real_socket(domain, type, protocol);
        if (fd >= 0) return fd;
        /* socket(AF_UNIX) blocked – fall back to socketpair(). */
        int sv[2];
        if (real_socketpair(domain, type, protocol, sv) == 0) {
            if (sv[0] >= 0 && sv[0] < 1024) {
                is_shimmed[sv[0]] = 1;
                peer_of[sv[0]]    = sv[1];
                int wp[2];
                if (pipe(wp) == 0) {
                    wake_r[sv[0]] = wp[0];
                    wake_w[sv[0]] = wp[1];
                }
            }
            return sv[0];
        }
        errno = EPERM;
        return -1;
    }
    return real_socket(domain, type, protocol);
}

/* ---- listen ---------------------------------------------------------- */
int listen(int sockfd, int backlog) {
    if (sockfd >= 0 && sockfd < 1024 && is_shimmed[sockfd]) {
        listener_fd = sockfd;
        return 0;
    }
    return real_listen(sockfd, backlog);
}

/* ---- accept ---------------------------------------------------------- */
int accept(int sockfd, struct sockaddr *addr, socklen_t *addrlen) {
    if (sockfd >= 0 && sockfd < 1024 && is_shimmed[sockfd]) {
        /* Block until close() writes to the wake pipe. */
        if (wake_r[sockfd] >= 0) {
            char buf;
            real_read(wake_r[sockfd], &buf, 1);
        }
        errno = ECONNABORTED;
        return -1;
    }
    return real_accept(sockfd, addr, addrlen);
}

/* ---- close ----------------------------------------------------------- */
int close(int fd) {
    if (fd >= 0 && fd < 1024 && is_shimmed[fd]) {
        int was_listener = (fd == listener_fd);
        is_shimmed[fd] = 0;

        if (wake_w[fd] >= 0) {              /* unblock accept() */
            char c = 0;
            write(wake_w[fd], &c, 1);
            real_close(wake_w[fd]);
            wake_w[fd] = -1;
        }
        if (wake_r[fd] >= 0) { real_close(wake_r[fd]); wake_r[fd]  = -1; }
        if (peer_of[fd] >= 0) { real_close(peer_of[fd]); peer_of[fd] = -1; }

        if (was_listener)
            _exit(0);                        /* conversion done – exit */
    }
    return real_close(fd);
}
"""



if __name__ == "__main__":
    import sys
    result = run_soffice(sys.argv[1:])
    sys.exit(result.returncode)
