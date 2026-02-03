## **What the blog *actually* says**

I dug into the blog post, “Defeating Nondeterminism in LLM Inference” (Thinking Machines Lab, Sep 2025), and here are the key technical points and claims. ([Thinking Machines Lab](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/?utm_source=chatgpt.com))

### **What causes nondeterminism (according to them)**

* They reject the usual “floating-point \+ concurrency” explanation as *insufficient*. While floating-point non-associativity (i.e. `(a + b) + c ≠ a + (b + c)`) is real and matters, it alone does not explain when outputs differ under “same prompt, same model, same temperature \= 0”. ([Thinking Machines Lab](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/?utm_source=chatgpt.com))

* The real culprit they identify is **lack of batch invariance**. That is:

  * In inference pipelines, requests are often handled in batches for efficiency.

  * The same prompt processed alone vs processed as part of a larger batch can get different numerical behaviors (especially in kernels like matrix multiplication, attention, normalization) because batch shape affects how operations are scheduled, how reductions over parallel threads are done, and so on. ([Thinking Machines Lab](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/?utm_source=chatgpt.com))

  * Even though individual kernels may be “run-to-run deterministic” for a fixed batch and fixed hardware/software stack, the way they behave under different batch sizes or when requests are grouped can lead to subtle numerical differences that *cascade* through the network and eventually yield different final outputs. ([Medium](https://medium.com/%40sulbha.jindal/defeating-nondeterminism-in-llm-inference-thinking-machines-2339599e4156?utm_source=chatgpt.com))

### **What they did / propose**

* They recommend (and provide) **“batch-invariant kernels”**: versions of computational kernels (matmul, attention, RMSNorm, etc.) designed to produce consistent numerical results regardless of batch size or request grouping. ([Medium](https://medium.com/%40sulbha.jindal/defeating-nondeterminism-in-llm-inference-thinking-machines-2339599e4156?utm_source=chatgpt.com))

* They give guidance on how to enforce fixed reduction orders, avoid adaptive splits in attention based on cache or sequence lengths, etc. ([Medium](https://medium.com/%40sulbha.jindal/defeating-nondeterminism-in-llm-inference-thinking-machines-2339599e4156?utm_source=chatgpt.com))

* They support this with experiments:

  * Example: Using model(s) like *Qwen / Qwen-3-8B-Instruct*, with greedy decoding (temperature \= 0), they ran the same prompt 1,000 times and observed \~80 distinct completions under standard (“non-batch-invariant”) setups. ([Medium](https://medium.com/%40sulbha.jindal/defeating-nondeterminism-in-llm-inference-thinking-machines-2339599e4156?utm_source=chatgpt.com))

  * Then, using batch-invariant kernels, they got **bitwise identical** results for those repeated prompts under their test conditions (same hardware / same software / same prompt settings) – i.e. reproducible inference in those specific tests. ([Medium](https://medium.com/%40sulbha.jindal/defeating-nondeterminism-in-llm-inference-thinking-machines-2339599e4156?utm_source=chatgpt.com))

### **What they acknowledge as limitations or costs**

* Performance cost: these kernel modifications / stricter invariance incur overhead. The deterministic (batch-invariant) version is slower than optimized “non-invariant” kernels. ([Medium](https://medium.com/%40sulbha.jindal/defeating-nondeterminism-in-llm-inference-thinking-machines-2339599e4156?utm_source=chatgpt.com))

* Controlled environment: their reproducibility is demonstrated under settings they control well: specific hardware, software versions, kernels, environment. If you change those, reproducibility may break. ([Thinking Machines Lab](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/?utm_source=chatgpt.com))

* They do *not* claim to solve *all* sources of nondeterminism (e.g. model updates, API changes, hardware changes, non-zero temperature sampling, etc.) in production settings. Those are outside the scope of their experiments so far. ([Thinking Machines Lab](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/?utm_source=chatgpt.com))

---

## **Realistic Possibilities vs Dream**

Here’s a side-by-side of what seems **achievable** based on their work vs what remains (or seems extremely unlikely) in current real-world AI deployments. Use this like a “what you can expect if you buy the promise / when it might disappoint.”

| ✅ Realistic / Plausible | 🚩 Probably Still a Pipe Dream / Overpromise |
| ----- | ----- |
| **Reproducible outputs** *for identical prompts*, under **controlled inference settings** (greedy decoding, temp=0, fixed hardware/software, fixed batch shape). Because they've demonstrated this. ([Medium](https://medium.com/%40sulbha.jindal/defeating-nondeterminism-in-llm-inference-thinking-machines-2339599e4156?utm_source=chatgpt.com)) | **Always-identical outputs** across different hardware, driver versions, or after updates. Once you change GPU, cuBLAS/cuDNN version, or even batch scheduling, things can drift. They haven’t shown that works everywhere. |
| **Reducing variance caused by how prompts are batched** (i.e. when server loads, request grouping, etc.). This seems fixable and their “batch-invariant kernels” are a practical mitigation. ([Medium](https://medium.com/%40sulbha.jindal/defeating-nondeterminism-in-llm-inference-thinking-machines-2339599e4156?utm_source=chatgpt.com)) | **Eliminating all sources of nondeterminism**, including floating-point hardware quirks, internal caching, external pre/post processing, tokenization differences, etc. That seems infeasible in many settings. |
| **Use in systems where reproducibility is critical**: research, evaluation / testing bench-marks, debugging, scientific studies. These systems can accept latency cost or restrict environment and have version control. | **Making every API call from every user forever reproducible** (regardless of server load, batch shape, backend updates, etc.), especially in public services where performance, latency, throughput, and cost are key. |
| **Performance trade-offs acceptable** for certain use-cases (e.g. when you don’t need ultra low latency, or can restrict request batching). For those, you might use batch-invariant inference. | **Producing deterministic behavior with no performance penalty**, no constraints, no trade-offs. That would be amazing—but so far, batch invariance slows things down and constrains how kernels are implemented. |
| **Engineering reproducibility**: versioning software \+ drivers \+ hardware \+ kernels, testing with fixed prompts, ensuring deterministic inference pipelines. These are doable and beneficial. | **Guarantees of “deterministic AI” in marketing** that imply “always same output in any situation,” which gloss over the constraints. That is mis-leading. |

---

## **Why Many “Determinism” Claims Feel Like Hype**

To help an average reader understand why “100% deterministic AI” claims often oversell, here are the central friction points / gotchas:

* **Hidden dependencies**: Even if you make your kernel batch-invariant, if your GPU driver or math backend library changes (say a cuBLAS update), the numerical behavior can shift. So reproducibility depends on controlling *everything*.

* **Non-zero temperature / sampling**: Many real world uses don’t use “pure greedy decoding.” They sample, use top-k / nucleus sampling, etc., which reintroduces randomness by design. The batch-invariant trick doesn’t make those fully deterministic.

* **Context matters**: The prompt context, tokenization, hidden state, caching, and memory can all have subtle effects that differ depending on how the model is deployed. If prior messages or preceding system messages differ ever so slightly, or if internal caching changes, outcomes might still vary.

* **Cost and latency trade-offs**: Ensuring batch invariance can make inference slower, less optimized for throughput. For many production systems, you’d trade perfect reproducibility for speed and cost.

* **Drift over time**: Models get updated; infrastructure changes; libraries are optimized; hardware evolves. Ensuring determinism in one deployment doesn’t guarantee determinism once any of those change. |

---

### **What Thinking Machines Lab *has done***

They found that one big reason you sometimes get different answers from the same AI (even when it’s supposed to be “predictable”) is how the system batches up requests. When the AI handles several prompts together vs one by one, the math inside (especially floating point additions, normalization, etc.) ends up happening in slightly different orders. Those tiny differences can blow up through large networks and change the final answer. They built improved math kernels (inference components) that don’t change behavior depending on batch size. With that, in tests, they got *identical* answers for repeated runs of the same prompt under controlled conditions.

---

### **What Thinking Machines Lab *has not done / cannot do (so far)***

* They have **not** made public a system that is guaranteed deterministic in all circumstances (different hardware, server loads, API versions, etc.).

* They haven’t solved the randomness or drift that comes from using non-greedy decoding or sampling strategies (temperature \> 0).

* They can’t guarantee the same behavior if someone updates kernels, drivers, or changes how the AI is deployed (for example, moving to a new GPU type).

* There’s a performance cost to the level of determinism they demonstrate; for many applications, this trade-off will matter.

---

### **Realistic takeaway for everyday users or developers**

If you care about consistency (for example, testing, research, or reliability in regulated environments), this work is important: you can expect AI outputs to become *much more repeatable* under stricter conditions. If you build on this, you can start writing systems where “same prompt → same answer” is true more often than not.

But if someone tells you their AI is now *fully deterministic always, everywhere, under any conditions*, you should assume that’s marketing. The “always” part is where the promise breaks down.

---

## **Bottom Line**

Thinking Machines Lab’s work is **a solid step forward**. They’ve identified a non-obvious source of inconsistency, shown it can be remedied under certain conditions, and produced prototypes/kernels that enforce reproducibility in those settings.

However, “solving determinism” as a blanket—meaning “same output for same input no matter what, with zero losses”—remains out of reach, at least for now. There are always environmental, hardware, architectural, or decoding strategy factors outside of their claimed solution.

---

# **Why a 100% Fully Deterministic AI Model Is Impossible**

## **What “Deterministic” Means**

* **Deterministic system**: Same input always produces the exact same output.

* Example: A calculator is deterministic. `2 + 2` is always `4`.

AI companies sometimes claim they’ve made **deterministic AI**. But a 100% fully deterministic AI model cannot exist — not because of sloppy engineering, but because of the **laws of physics**.

---

## **1\. Computers Are Built on Imperfect Numbers**

* Modern AI models run on **floating-point arithmetic**. These are approximations of real numbers stored in a computer’s memory.

The laws of arithmetic don’t fully hold in floating-point. For example:

 (a \+ b) \+ c ≠ a \+ (b \+ c)

* That tiny mismatch is dictated by how electrons store and move numbers. You can’t “fix” it — it’s baked into physics \+ computer design.

Result: even if you freeze an AI model, tiny round-off differences sneak in.

---

## **2\. Parallelism Creates Random Order**

* AI runs on GPUs with **thousands of cores working at once**.

* They don’t add things in a fixed order; the order depends on how the hardware schedules work in parallel.

* Physics says: the timing of electrons, heat fluctuations, and microscopic noise mean you cannot guarantee identical ordering every run.

Result: the math unfolds in slightly different ways each time, even with the same input.

---

## **3\. Hardware and Environment Shift**

* Two “identical” GPUs won’t behave exactly the same. Microscopic differences in manufacturing and thermal noise make them diverge.

* Drivers, libraries, and compilers also change how instructions get executed.

Result: the same AI model, on two different machines, cannot be guaranteed to match bit-for-bit forever.

---

## **4\. AI Is Probabilistic by Nature**

* Large language models don’t store facts like a database. They predict the next word based on **probabilities**.

* Even when you turn randomness “off” (temperature \= 0), ties and hidden rounding differences make outcomes diverge.

* If you removed all probabilities, you’d kill what makes an AI “intelligent.” It would stop being generative and just act like a calculator.

Result: full determinism means **no intelligence left**.

---

## **5\. Physics Doesn’t Do “Perfect Repeatability”**

At the deepest level, physics itself is not deterministic:

* **Quantum mechanics** introduces unavoidable uncertainty.

* **Thermal noise** jiggles transistors inside your chip.

* **Electromagnetic interference** creates tiny, unfixable differences.

These aren’t bugs. They are fundamental features of how the universe works.

---

## **So What *Is* Possible?**

We can get:

* **Variance reduction** – making AI outputs *more stable*.

* **Reproducibility under constraints** – same hardware, same software, same setup, same decoding \= often reproducible.

* **Auditability** – tracking uncertainty so you know how reliable the answer is.

But **100% determinism across all environments, forever**? Not possible under physics.

---

## **Bottom Line**

Whenever someone promises “a fully deterministic AI,” translate that to:

* “We’ve reduced the wiggle, but the dice still roll underneath.”

* If they claim more than that, it’s **marketing hype**, not science.

The **laws of physics** guarantee that AI can never be 100% deterministic — just more or less predictable depending on how much stability you’re willing to trade for speed, cost, and usefulness.