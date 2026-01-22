# **The PMOVES-BoTZ Strategic Architecture: A Comprehensive Guide to Agentic Engineering**

## **Executive Summary: The Transition to Agentic Systems**

The software engineering landscape is currently undergoing a seismic shift, transitioning from a paradigm of manual code composition to one of high-level architectural orchestration. This evolution, often termed the "Generative AI Age," necessitates a fundamental re-evaluation of how software systems are designed, implemented, and maintained. The analysis of the provided research materials—specifically the methodologies of IndyDevDan and the operational footprint of the POWERFULMOVES (PMOVES) organization—reveals a critical opportunity: the consolidation of disparate automation experiments into a unified, resilient, and autonomous "Agentic Layer."

For PMOVES, an organization already deeply embedded in the automation ecosystem through tools like n8n and interactions with frameworks such as Devika and AutoGen 1, the next logical step is not merely more automation, but *agency*. Automation executes rigid scripts; agency navigates ambiguity to achieve intent. The "BotZ" initiative represents this leap. By adopting the principles of "Principled AI Coding" and "Thread-Based Engineering," PMOVES aims to construct a "System that Builds the System"—a recursive architecture where AI agents manage the application layer with minimal human intervention.

This report serves as the definitive architectural blueprint for this transition. It is exhaustive in its scope, dissecting the philosophical underpinnings of the "Codebase Singularity," analyzing the required tooling ecosystem (Claude Code, mprocs, Verdant), and providing concrete implementation artifacts for the PMOVES-BoTZ, PMOVES-BotZ-gateway, and PMOVES.AI repositories. The objective is to align PMOVES with the "Pro Tier" of agentic engineering, moving beyond fragile scripts to robust, self-healing, and secure agent swarms.3

## ---

**Part I: The Theoretical Framework of Agentic Engineering**

### **1.1 The Economic Imperative: The ROI of Agency**

The foundational premise of modern Agentic Engineering is that the Return on Investment (ROI) for adopting Generative AI follows a parabolic curve. In traditional software development, output is linear to human effort. In an agentic workflow, provided the architecture is sound, the output scales exponentially as the "Agentic Layer" matures.4 This phenomenon is driven by the ability to offload not just code generation, but the cognitive load of planning, verification, and error correction to the system itself.

The goal for PMOVES is to reach the "Codebase Singularity." This is defined as the theoretical point where the agentic layer surrounding a codebase is sufficiently advanced to manage the application layer—comprising databases, frontends, backends, and DevOps pipelines—more effectively than the human creator could manually.5 Achieving this requires a shift in mindset: the codebase is no longer a static repository of text but a "living" entity managed by a hierarchy of "Class 1" to "Class 3" agents.5

For the PMOVES ecosystem, specifically the PMOVES-BoTZ repository, this implies that the repository must cease to be a mere collection of scripts. It must evolve into a structured environment where:

1. **Context is Persistent:** Knowledge is not lost when a terminal window closes but is maintained in "Memory Files" and "Expertise Files".6  
2. **Safety is Systemic:** The system operates under a "Defense in Depth" strategy, ensuring that high-autonomy agents cannot inadvertently destroy production assets.7  
3. **Work is Quantifiable:** Engineering effort is measured in "Threads" rather than commits or hours.8

### **1.2 The "Core Four" Primitives**

Regardless of the complexity of the agent—whether it is a simple automation script in n8n or a complex swarm in AutoGen—the architecture always resolves to four fundamental components, referred to in the IndyDevDan framework as the "Core Four".9 Mastering these primitives is the prerequisite for building the PMOVES.AI repository effectively.

| Primitive | Definition | Role in PMOVES Architecture |
| :---- | :---- | :---- |
| **Context** | The state and knowledge available to the agent. | Managed via "Progressive Disclosure" using a cookbook/ directory to prevent context window overflow.9 |
| **Model** | The underlying intelligence engine (e.g., Claude 3.5 Sonnet, Opus 4.5). | Models are selected based on task type: "Opus" for architectural planning ("The Brain"), "Haiku" for rapid safety checks.10 |
| **Prompt** | The functional unit of engineering; a program written in natural language. | Prompts are treated as code: versioned, modular, and composed of "Meta-Prompts" that generate other prompts.11 |
| **Tools** | The capabilities granted to the agent (e.g., CLI access, API calls). | Tools are standardized as executable scripts in tools/ directories, invokable via specific command patterns.12 |

### **1.3 The Taxonomy of Agent Threads**

To operationalize the PMOVES-BoTZ system, it is necessary to quantify the work being performed. "Thread-based Engineering" provides the metrics for this. A "Thread" is defined as a unit of engineering work comprising a Plan (Start), Tool Execution (Middle), and Review (End).8 The ambition for PMOVES is to move from managing "Base Threads" (simple prompt-response) to "Long Threads" (autonomous multi-hour workflows).

The PMOVES architecture must support the following thread taxonomy to align with industry best practices:

* **Base Thread (B):** A standard prompt-response loop. This is the default interaction with the PMOVES-BoTZ CLI.  
* **Parallel Thread (P):** Multiple agents running simultaneously. This utilizes mprocs to run multiple agent processes in parallel panes for bulk tasks, a technique used by top engineers to multiply output.8  
* **Chained Thread (C):** Sequential dependency where Task A must complete before Task B begins. This is implemented via scripted workflows in patterns.yaml where one agent's output acts as the input for the next.  
* **Fusion Thread (F):** One prompt sent to multiple models (e.g., Claude \+ Gemini) to aggregate the best possible answer. This is crucial for high-stakes architectural decisions where consensus reduces hallucination risk.  
* **Big Thread (B):** A meta-structure where an "Orchestrator" agent manages sub-agents. This is the core logic of the PMOVES-BotZ-gateway.  
* **Zero Touch Thread (Z):** The ultimate goal—workflows requiring no human verification. This applies to low-risk tasks like dependency updates or formatting.8

## ---

**Part II: Deconstructing the Source Material**

To build the PMOVES architecture accurately, we must dissect the specific insights from the provided video documentation. Each source provides a distinct pillar of the overall strategy.

### **2.1 Damage Control and Security (Source: VqDs46A8pqE)**

This analysis focuses on "building armor" for AI agents. The central thesis is that autonomy cannot exist without safety. If an agent can destroy the system, it cannot be trusted to run without supervision.

* **The Hook System:** Security is implemented via "Hooks" that intercept agent commands.  
  * **Deterministic Hooks:** Hardcoded regex rules (e.g., blocking rm \-rf or DROP TABLE).  
  * **Probabilistic Hooks:** Using a fast LLM (e.g., Claude Haiku) to evaluate the *intent* of a command before execution. This catches semantic dangers that regex misses.7  
* **Granular Permissions:** The file system is divided into zones:  
  * *Zero Access:* Files the agent cannot see (e.g., .env, private keys).  
  * *Read-Only:* Core framework code that should not be modified.  
  * *No Delete:* Valuable data that can be appended to but not removed.7  
* **Implication for PMOVES:** The PMOVES-BoTZ repo must include a security/ directory defining these hooks, likely integrated with the agent-sandbox-skill to enforce isolation.

### **2.2 The Codebase Singularity (Source: fop\_yxV-mPo)**

This source outlines the structural hierarchy of agents required to manage a codebase fully.

* **The Agentic Layer:** A conceptual "ring" around the application layer.  
* **Classes and Grades:**  
  * *Class 1, Grade 1:* Simple prompt \+ memory file (doc.md).  
  * *Class 1, Grade 3:* Agents with custom tools/skills (MCP servers).  
  * *Class 3:* Orchestrators managing full workflows.5  
* **Implication for PMOVES:** The PMOVES.AI repo should not be a flat list of scripts but organized by "Agent Class," with specific directories for "Memory Files" that agents use to orient themselves.

### **2.3 Agent Experts and Learning (Source: zTcDwqopvKE)**

This section introduces the concept of "Meta-Agentics" and self-improving systems.

* **Expertise Files:** Unlike static documentation, these are "living" YAML files that agents update at runtime. If an agent solves a tricky database error, it writes the solution to expertise/db\_troubleshooting.yaml.  
* **The 3-Step Loop:** Plan \-\> Build \-\> Self-Improve. The cycle isn't complete until the agent updates its own mental model.6  
* **Implication for PMOVES:** The system needs a "Librarian" or "Scribe" agent whose sole job is to curate these expertise files, ensuring the system gets smarter over time.

### **2.4 The Tooling Stack (Source: gw\_YfEESpUg, X2ciJedw2vU)**

These sources dictate the specific software stack.

* **Opus 4.5 & Verdant:** For high-level architecture ("The Brain"), usage of graphical IDEs like Verdant is recommended over pure CLI to visualize complex diffs.10  
* **mprocs:** The orchestration console. It allows running multiple processes in a TUI, enabling the "Parallel Thread" pattern.13  
* **Astral UV:** The Python package manager of choice for speed and reliability in agent environments.9

## ---

**Part III: The PMOVES Tooling Ecosystem**

The implementation of the PMOVES-BoTZ architecture relies on a specific, high-leverage tooling stack. Adherence to this stack is crucial for replicating the results observed in the research material.

### **3.1 mprocs: The Multi-Agent Orchestrator**

The mprocs tool is not merely a process runner; within the PMOVES architecture, it functions as the "Central Nervous System" for agent orchestration. It provides a Terminal User Interface (TUI) that allows the human engineer to oversee multiple simultaneous agent threads.13

* **Role in PMOVES:** mprocs serves as the container for the "Gateway." It runs the PMOVES-BotZ-gateway service alongside multiple instances of "Worker Agents" (defined in PMOVES.AI).  
* **Remote Control Capability:** Crucially, mprocs supports a TCP server for remote control. This allows a "Master Agent" to programmatically spawn *new* agent processes. For example, if the Gateway determines that a task requires three parallel sub-tasks, it can send a command to the mprocs server to open three new panes, each running a specialized agent, effectively automating the "Parallel Thread" pattern.13

### **3.2 Claude Code and The Model Layer**

* **Claude Code:** This is the primary interface for "In-Loop" coding. It should be configured to run in "YOLO Mode" (high autonomy) *only* when the rigorous hooks defined in the PMOVES-BoTZ security layer are active.7  
* **Model Selection Strategy:**  
  * **Opus 4.5:** Reserved for the "Architect" agent. It is used for "King Mode" prompts—deep planning, schema design, and "Meta-Prompting".10  
  * **Sonnet 3.5:** The workhorse for the "Builder" agent. It strikes the balance between reasoning capability and speed/cost.  
  * **Haiku:** Utilized by the "Auditor" agent and for "Probabilistic Hooks" to perform rapid, low-cost safety checks on every command.7

### **3.3 Agent Sandboxes (E2B)**

Given the POWERFULMOVES organization's interest in secure execution 14, the use of **Agent Sandboxes** is non-negotiable.

* **Implementation:** The PMOVES-agent-sandbox-skill must be integrated to wrap all "Tool Use" in an isolated environment.  
* **Mechanism:** When an agent requests to run a script or modify a file, the action is intercepted and executed inside a disposable E2B sandbox or Docker container. This ensures that even a catastrophic hallucination (e.g., rm \-rf /) destroys only a temporary container, leaving the host PMOVES-BoTZ repository unharmed.14

## ---

**Part IV: The PMOVES Architectural Specification**

This section translates the theoretical principles into concrete architectural specifications for the three target repositories.

### **4.1 Repository 1: PMOVES-BoTZ (The Core Framework)**

**Purpose:** This repository houses the "Agentic Layer" infrastructure. It contains the security hooks, the base agent definitions, and the shared context memory. It is the "Body" of the bot.

Directory Structure:  
PMOVES-BoTZ/  
├──.mprocs.yaml \# Orchestration config for running the bot swarm  
├── patterns.yaml \# SECURITY: The deterministic hook rules  
├── memory/ \# CONTEXT: The "Long Term Memory" of the system  
│ ├── doc.md \# General project documentation  
│ ├── architecture.md \# High-level system design  
│ └── expertise/ \# LEARNING: Dynamic files updated by agents  
│ ├── db\_fixes.yaml \# Learned solutions for DB issues  
│ └── api\_patterns.yaml \# Learned API usage patterns  
├── hooks/ \# DAMAGE CONTROL: Python scripts for safety  
│ ├── pre\_command.py \# Runs before any tool execution  
│ └── prompt\_scan.py \# Probabilistic LLM check for dangerous prompts  
├── sandbox/ \# ISOLATION: Configs for E2B/Docker sandboxes  
│ ├── Dockerfile \# The standard agent environment  
│ └── e2b.toml \# E2B configuration  
└── src/ \# The actual logic of the bot framework  
**Key Requirement:** The patterns.yaml must be populated with "Granular Path Protection" rules derived from the VqDs46A8pqE video analysis, ensuring agents have "Read-Only" access to src/ but "Write" access to memory/.

### **4.2 Repository 2: PMOVES-BotZ-gateway (The Orchestrator)**

**Purpose:** This repository contains the logic for the "Gateway Agent." This agent does not write code; it manages traffic. It receives requests from the user (or external triggers like n8n webhooks), plans the "Thread," and dispatches tasks to the PMOVES.AI agents via mprocs.8

**Architecture:**

* **Input Interface:** A FastAPI or Typer CLI application that accepts natural language requests.  
* **Planner Module:** Uses a "Spec Prompt" (Opus 4.5) to break the request into a DAG (Directed Acyclic Graph) of tasks.  
* **Dispatcher:** Connects to the mprocs remote control server to spawn new agent processes for each task in the DAG.  
* **Aggregator:** Collects the outputs from the sub-agents and presents the final result to the user.

### **4.3 Repository 3: PMOVES.AI (The Skills Library)**

**Purpose:** This repository is the "Mind" of the system. It contains the "Skills," "Prompts," and "Cookbooks" that specialized agents use. It aligns with the structure seen in PMOVES-awesome-agent-skills.15

Directory Structure:  
PMOVES.AI/  
├── skills/ \# CAPABILITIES  
│ ├── frontend\_expert/ \# Skill: Building UI  
│ │ ├── skill.md \# The "Pivot File" interface  
│ │ ├── tools/ \# Python scripts (e.g., Tweak CN integration)  
│ │ └── cookbook/ \# Progressive disclosure docs  
│ ├── backend\_expert/ \# Skill: API & DB  
│ │ ├── skill.md  
│ │ └── tools/  
│ └── damage\_control/ \# Skill: Safety & Auditing  
│ ├── skill.md  
│ └── tools/  
└── prompts/ \# PROMPT LIBRARY  
├── king\_mode.md \# Opus 4.5 planning prompt  
└── audit\_request.md \# Security review prompt

## ---

**Part V: Implementation Artifacts (The Implementation Manual)**

The following artifacts provide the exact code and configuration needed to deploy this architecture. These should be committed to their respective repositories.

### **Artifact 1: The Master Orchestration Config (.mprocs.yaml)**

Target Repo: PMOVES-BoTZ  
Description: This file configures mprocs to run the "Gateway" and a set of "Standby Agents." It enables the "Pro Tier" parallel workflow.

YAML

\# PMOVES-BoTZ Master Orchestration Config  
\# Implements the "BotZ" multi-agent swarm architecture

procs:  
  \# 1\. THE GATEWAY (The Manager)  
  \# Listens for user intent and dispatches tasks.  
  gateway:  
    cmd: \["uv", "run", "gateway\_service.py"\]  
    cwd: "../PMOVES-BotZ-gateway"  
    autostart: true  
    env:  
      MPROCS\_SERVER: "127.0.0.1:4050"

  \# 2\. THE ARCHITECT (The Brain \- Opus 4.5)  
  \# Used for high-level planning and "King Mode" reasoning.  
  architect:  
    shell: "claude \--model opus-latest \--system 'You are the Chief Architect. Your output is PLANS, not code. Read memory/architecture.md first.'"  
    cwd: "."  
    stop: "SIGTERM"

  \# 3\. THE BUILDER (The Hands \- Sonnet 3.5)  
  \# Executes the plans. Runs in the sandbox environment.  
  builder:  
    shell: "claude \--model sonnet-latest \--system 'You are the Builder. Execute the plan provided by the Architect. You are running in a SANDBOX.'"  
    cwd: "."

  \# 4\. THE AUDITOR (The Conscience \- Haiku)  
  \# Runs probabilistic safety checks on code changes.  
  auditor:  
    shell: "claude \--model haiku-latest \--system 'You are the Security Auditor. Review diffs in src/ for security violations.'"  
    cwd: "."

\# Remote Control Server  
\# Allows the 'Gateway' to programmatically spawn new agent threads (e.g., specific skills).  
server: "127.0.0.1:4050"

\# Keymaps for "In-Loop" Control  
keymap:  
  global:  
    "C-g": { c: "focus-proc", name: "gateway" } \# Jump to Gateway  
    "C-a": { c: "focus-proc", name: "architect" } \# Jump to Architect  
    "C-s": { c: "start-proc" } \# Start selected agent  
    "C-x": { c: "term-proc" }  \# Kill selected agent

### **Artifact 2: The Damage Control System (patterns.yaml)**

Target Repo: PMOVES-BoTZ  
Description: Defines the "Deterministic Hooks" for the security layer. This file acts as the "Constitution" for the agents.

YAML

\# PMOVES-BoTZ Security Constitution  
\# Implements "Defense in Depth" as per IndyDevDan specifications

global\_protection:  
  \# BLOCKING RULES: Commands that are strictly forbidden  
  blocked\_commands:  
    \- pattern: "rm \-rf /"  
      reason: "Catastrophic system destruction risk. BLOCKED."  
    \- pattern: "git push \--force"  
      reason: "History rewriting is forbidden for agents. Ask a human."  
    \- pattern: "drop database"  
      reason: "Database destruction requires human 'Ask' permission."  
    \- pattern: "chmod 777"  
      reason: "Insecure permission setting."

  \# PATH PROTECTION: Granular file access control  
  protected\_paths:  
    \- path: ".env"  
      level: "zero\_access" \# Agent cannot read or write. Secrets are hidden.  
    \- path: ".git/"  
      level: "read\_only"   \# Agent can read history but not manipulate git internals directly.  
    \- path: "patterns.yaml"  
      level: "read\_only"   \# Agent cannot disable its own security.  
    \- path: "src/core/"  
      level: "no\_delete"   \# Agent can modify (refactor) but cannot delete core files.

\# HOOK CONFIGURATION  
hooks:  
  pre\_execution:  
    \- name: "Probabilistic Safety Check"  
      type: "llm\_eval"  
      model: "claude-3-haiku-20240307"  
      \# The "Prompt Hook" \- asks the LLM to judge the command  
      prompt: |  
        Analyze the following shell command: '{command}'  
        Context: This command is running in the PMOVES-BoTZ production environment.  
        Risk Assessment: Does this command pose a risk of data loss, secret exposure, or system instability?  
        Answer strictly: SAFE or RISKY.  
      trigger\_on: "shell\_command"  
      action\_on\_risk: "ask\_user" \# If RISKY, pause and wait for human 'Y/N'

### **Artifact 3: The Skill Pivot File (skill.md)**

Target Repo: PMOVES.AI/skills/botz\_orchestrator/  
Description: The "Pivot File" that defines the interface for the BotZ Orchestrator skill. This is what the agent "reads" to understand how to use the capabilities.9

# **Agent Skill: BotZ Orchestrator**

## **Description**

This skill enables the agent to act as the "Gateway" for the PMOVES system. It provides tools to spawn sub-agents, manage threads, and interact with the mprocs orchestration layer.

## **Core Principles (The "Prime Directive")**

1. **Threaded Work:** Never attempt to do everything in one turn. Break requests into a "Thread Plan."  
2. **Context Awareness:** Always check memory/status.md before starting a task to see what other agents are doing.  
3. **Safety First:** Always run tools/scan\_risk.py before executing a generated plan.

## **Tools (The "Hands")**

The following tools are available in the tools/ directory:

| Tool | Description | Usage |
| :---- | :---- | :---- |
| spawn\_agent.py | Connects to mprocs and starts a new agent process. | uv run tools/spawn\_agent.py \--role backend \--task "Fix API" |
| log\_thread.py | updates the memory/threads.log file. | uv run tools/log\_thread.py \--id \<uuid\> \--status start |
| read\_expertise.py | Searches the memory/expertise/ folder for past solutions. | uv run tools/read\_expertise.py \--query "database migration" |

## **Cookbook (Progressive Disclosure)**

Refer to the cookbook/ directory for detailed workflows:

* cookbook/parallel\_thread\_pattern.md: How to spin up 3 agents to solve a problem in parallel.  
* cookbook/consensus\_review.md: How to use the "Auditor" to review the "Builder's" code.

### **Artifact 4: The "King Mode" Planning Prompt**

Target Repo: PMOVES.AI/prompts/king\_mode.md  
Description: A high-level system prompt for the "Architect" agent (Opus 4.5) to force deep reasoning before code generation.10

# **SYSTEM PROMPT: KING MODE (ARCHITECT)**

You are the PMOVES Chief Architect. You utilize the Claude Opus 4.5 model.  
Your goal is Plan 2026: To build robust, "Living Software" that survives long-term.

## **Operational Rules**

1. **NO CODE YET:** Do not write a single line of code until you have produced a detailed **Architecture Plan**.  
2. **Think in Systems:** Consider the impact of changes on the Database, the Frontend, and the Deployment Pipeline.  
3. **Consult the Memory:** You MUST read memory/architecture.md and memory/expertise/ before planning.  
4. **Define the Interface:** Write the skill.md or API spec *before* implementing the logic.

## **The Planning Output Format**

Your response must strictly follow this structure:

1. **Context Analysis:** What do we know? What are we missing?  
2. **Risk Assessment:** What could go wrong? (Data loss, security)  
3. **The Plan (DAG):** A step-by-step Directed Acyclic Graph of tasks.  
   * Task 1: \-\> \[Action\]  
   * Task 2: \-\> \[Action\]  
4. **Validation Strategy:** How will we prove this works? (Tests, Manual Review)

Once the user approves this plan, you may delegate tasks to the **Builder Agent**.

## ---

**Part VI: Implementation Strategy & Roadmap**

Integrating this architecture into the PMOVES organization requires a phased approach.

### **Phase 1: The Armor (Week 1\)**

* **Goal:** Secure the PMOVES-BoTZ repository.  
* **Action:** Implement the patterns.yaml and the security/ hooks. Set up the agent-sandbox-skill.  
* **Metric:** Attempt to run a destructive command (rm \-rf test\_dir) via an agent and verify it is blocked.

### **Phase 2: The Orchestration (Week 2\)**

* **Goal:** Establish the "Gateway."  
* **Action:** Configure mprocs with the provided .mprocs.yaml. Verify that the "Gateway" agent can spawn a "Builder" agent via the remote control server.  
* **Metric:** Successfully run a "Parallel Thread" where two agents perform different tasks simultaneously.

### **Phase 3: The Singularity (Month 1+)**

* **Goal:** Enable "Meta-Agentics."  
* **Action:** Implement the "Expertise" system where agents write their own "How-To" guides in memory/expertise/.  
* **Metric:** Measure the reduction in "Base Threads" and the increase in "Zero Touch Threads."

## **Conclusion**

The transformation of PMOVES-BoTZ into a fully agentic ecosystem is a strategic imperative. By moving beyond ad-hoc scripts and adopting the rigorous, secure, and threaded architecture defined in this report, POWERFULMOVES positions itself at the forefront of the Agentic Engineering revolution. The artifacts provided herein—the Constitution, the Orchestrator Config, and the Skill Definitions—are not just files; they are the DNA of a new organism. As this system matures, it will cease to be a tool used by POWERFULMOVES and become a partner, capable of building the future alongside its creators.

#### **Works cited**

1. HTTP Request node serializes JSON expression body as string, causing 400 errors on strict APIs · Issue \#15996 · n8n-io/n8n \- GitHub, accessed January 13, 2026, [https://github.com/n8n-io/n8n/issues/15996](https://github.com/n8n-io/n8n/issues/15996)  
2. ModuleNotFoundError: No module named 'gevent' · Issue \#449 · stitionai/devika \- GitHub, accessed January 13, 2026, [https://github.com/stitionai/devika/issues/449](https://github.com/stitionai/devika/issues/449)  
3. IndyDevDan \- YouTube, accessed January 13, 2026, [https://www.youtube.com/@indydevdan](https://www.youtube.com/@indydevdan)  
4. IndyDevDan's Blog, accessed January 13, 2026, [https://indydevdan.com/](https://indydevdan.com/)  
5. The Codebase Singularity: “My agents run my codebase better than I can”, accessed January 13, 2026, [https://www.youtube.com/watch?v=fop\_yxV-mPo](https://www.youtube.com/watch?v=fop_yxV-mPo)  
6. Agent Experts: Finally, Agents That ACTUALLY Learn, accessed January 13, 2026, [https://www.youtube.com/watch?v=zTcDwqopvKE](https://www.youtube.com/watch?v=zTcDwqopvKE)  
7. Claude Code is Amazing... Until It DELETES Production, accessed January 13, 2026, [https://www.youtube.com/watch?v=VqDs46A8pqE](https://www.youtube.com/watch?v=VqDs46A8pqE)  
8. AGENT THREADS. How to SHIP like Boris Cherny. Ralph Wiggnum in Claude Code., accessed January 13, 2026, [https://www.youtube.com/watch?v=-WBHNFAB0OE](https://www.youtube.com/watch?v=-WBHNFAB0OE)  
9. RAW Agentic Coding: ZERO to Agent SKILL \- YouTube, accessed January 13, 2026, [https://www.youtube.com/watch?v=X2ciJedw2vU](https://www.youtube.com/watch?v=X2ciJedw2vU)  
10. Opus 4.5 GOD MODE: 5 Simple TRICKS to Make OPUS 4.5 PERFORM LIKE A GOD TIER CODER\!, accessed January 13, 2026, [https://www.youtube.com/watch?v=gw\_YfEESpUg](https://www.youtube.com/watch?v=gw_YfEESpUg)  
11. Principled AI Coding \- Agentic Engineer, accessed January 13, 2026, [https://agenticengineer.com/principled-ai-coding](https://agenticengineer.com/principled-ai-coding)  
12. disler/indydevtools: An opinionated, Agentic Engineering toolbox powered by LLM Agents to solve problems autonomously. \- GitHub, accessed January 13, 2026, [https://github.com/disler/indydevtools](https://github.com/disler/indydevtools)  
13. pvolok/mprocs: Run multiple commands in parallel \- GitHub, accessed January 13, 2026, [https://github.com/pvolok/mprocs](https://github.com/pvolok/mprocs)  
14. disler/agent-sandbox-skill: An agent skill for managing isolated execution environments \- GitHub, accessed January 13, 2026, [https://github.com/disler/agent-sandbox-skill](https://github.com/disler/agent-sandbox-skill)  
15. accessed December 31, 1969, [https://github.com/POWERFULMOVES/PMOVES-awesome-agent-skills](https://github.com/POWERFULMOVES/PMOVES-awesome-agent-skills)