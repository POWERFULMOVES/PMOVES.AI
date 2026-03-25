FROM nginx:alpine@sha256:e7257f1ef28ba17cf7c248cb8ccf6f0c6e0228ab9c315c152f9c203cd34cf6d1

# Security: Run as non-root user
RUN addgroup -g 65532 -S pmoves && \
    adduser -u 65532 -S pmoves -G pmoves && \
    chown -R pmoves:pmoves /var/cache/nginx /var/log/nginx /etc/nginx/conf.d && \
    touch /var/run/nginx.pid && \
    chown -R pmoves:pmoves /var/run/nginx.pid

COPY default.conf /etc/nginx/conf.d/default.conf

USER pmoves:pmoves
