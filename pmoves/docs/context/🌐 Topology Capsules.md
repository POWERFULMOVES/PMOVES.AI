# **🌐 Topology Capsules — General Overview Explainer**

### **What are Topology Capsules?**

Imagine looking at a cloud of points — like stars in the night sky. Some points are close together, some are far apart, and there’s an invisible *shape* to the whole cloud. Topology Capsules are a way of capturing that shape, then using it to make decisions or predictions, even when we have very few labels (answers) to guide us.

Instead of training a huge neural network with millions of parameters, we let the data’s own **geometry** — its natural structure — tell us how it wants to be organized.

---

### **Key Ideas**

#### **1\. Positive and Negative Relationships**

* **Positive links (KNN):** Who is close to whom? These capture *similarities*.

* **Negative links (KFN):** Who is definitely not alike? These capture *differences*.

Traditional AI mostly focuses on similarity. Topology Capsules bring in **repulsion** too, balancing attraction and separation. It’s like mapping friendships *and* rivalries in a social network.

---

#### **2\. Multi-View Consensus**

Looking at data just one way can be misleading. To reduce noise, we rotate and jitter the data into several “views.” We only keep the connections that show up consistently across views.

This is like asking multiple friends for directions: if everyone agrees on the same turns, you know it’s probably the right path.

---

#### **3\. Capsules as Frozen Structures**

A “capsule” here is not a neural unit but a **spectral fingerprint** of the data — a frozen snapshot of its shape. Once built, the capsule does not change. Labels (like “cat” or “dog”) are used only to *probe* this structure, never to reshape it.

This makes the method very **robust and interpretable**: the capsule is what the data inherently is, not what labels force it to be.

---

#### **4\. Label Propagation**

Suppose you know the species of just a few animals in a zoo. With capsules, you can spread (“propagate”) those known labels through the graph of relationships to make educated guesses about the others.

This is how Topology Capsules achieve good accuracy with very few labels — they let the geometry of the data do most of the work.

---

#### **5\. Ensembles and Stability**

For trickier datasets (like telling cats and dogs apart), multiple capsules can be built from different “views” (silhouette, texture, structure, etc.).

* Each capsule makes its own guess.

* Their predictions are calibrated and weighted by how *stable* they are under small perturbations.

* Then they are blended together, like a jury reaching consensus.

This makes the final system more reliable than any single view alone.

---

### **Why It’s Different**

* **No heavy training loops** — doesn’t require backpropagation or GPUs.

* **Few labels needed** — can work with just dozens of examples per class.

* **Geometry-first approach** — directly uses the shape of the data.

* **Interpretable** — capsules can be inspected through their eigenvalues and components (a bit like “listening to the harmonics” of the dataset).

---

### **Everyday Analogy**

Think of a **school cafeteria**:

* Kids who sit together every day form **positive links**.

* Kids who avoid each other form **negative links**.

* By observing these seating patterns from multiple angles (lunch, recess, class), you can figure out the school’s social structure.

* If you learn that just a few kids are in “chess club” or “soccer team,” you can spread those labels through the seating graph to guess which other kids belong.

That’s essentially what Topology Capsules do — at the scale of complex datasets.

---

### **Applications**

* Classifying images when labels are scarce.

* Analyzing the *shape* of datasets in science (e.g., biology, physics).

* Building lightweight AI systems that run on laptops or edge devices.

* Creating interpretable models where users can see the underlying structure.


# **🌀 Technical Release Document**

## **Topology Capsules v1.0**

### **Release Date**

August 2025

---

## **1\. Introduction**

Topology Capsules v1.0 is a new framework for **graph-based learning without training loops**, designed for semi-supervised and low-label regimes. Unlike conventional deep learning pipelines, Topology Capsules capture the **geometric and topological structure** of data through signed graph Laplacians. Labels only *probe* these capsules rather than shaping them, resulting in lightweight, interpretable, and robust inference.

---

## **2\. Core Concepts**

### **2.1 Capsules as Graph Spectra**

* A **Topology Capsule** is defined as a frozen spectral basis extracted from the positive graph Laplacian.

* Capsules encode the intrinsic *shape of the data manifold*, independent of labels.

* Once constructed, capsules are probed via label propagation (LP) to infer class posteriors.

### **2.2 Positive and Negative Graphs**

* **KNN(+) Graphs**: Built from nearest-neighbor consensus across multiple random projections. Capture similarity.

* **KFN(−) Graphs**: Built from farthest-neighbor consensus. Capture dissimilarity and provide repulsive constraints.

* The signed Laplacian combines both into a balanced representation.

### **2.3 Affinity Calibration**

* Positive affinities use **Zelnik–Manor local scaling** for adaptive neighborhood bandwidth.

* Negative affinities are normalized using **robust z-scores** and a **soft sigmoid repulsion**.

* Multi-view consensus ensures only stable edges persist.

### **2.4 Label Propagation**

* Capsules are never updated by labels.

* LP solves a sparse system `(L + λL− + ridge*I) F = Y`, where:

  * `L` \= positive Laplacian

  * `L−` \= negative Laplacian (repulsion)

  * `λ` \= repulsion weight

  * `ridge` \= regularization parameter

* Hyperparameters `(λ, ridge)` are tuned *only on labeled seeds*.

---

## **3\. Key Features in v1.0**

1. **Consensus-Based Capsule Construction**

   * Multi-view embeddings via random orthonormal rotations and jitter.

   * Edges must be mutual and consistent across views.

2. **Dual Graph Modeling**

   * Attractive forces: KNN(+).

   * Repulsive forces: KFN(−).

3. **Adaptive Affinities**

   * Positive edges scaled by local σ.

   * Negative edges softened by z-score distributions.

4. **Frozen Capsules**

   * Capsules (spectral bases) are fixed once built.

   * Prevents label leakage into data representation.

5. **Seed-Only Auto-Tuning**

   * No reliance on validation labels.

   * Hyperparameters tuned via log-likelihood on seeds.

6. **Internal Transfer**

   * Capsules support transfer to new splits or test slices via kNN pull in spectral space.

---

## **4\. Benchmarks**

### **4.1 Fashion-MNIST**

* **Setup**: Pixels → PCA (64D) → Topology Capsule.

* **Performance**:

  * KNN-only LP: \~0.74 accuracy.

  * Signed LP (auto-tuned): \~0.81 accuracy with only 40 labels per class.

### **4.2 CIFAR-10 (Fast Capsule, CPU-only)**

* **Features**: HOG descriptors \+ simple color stats.

* **Performance**:

  * KNN-only baseline: \~0.56 accuracy.

  * Capsule with signed LP: \~0.63 accuracy with 30 labels per class.

* Runtime: \~45–60s on Colab CPU for 4k samples.

### **4.3 Cat vs Dog Subset (CIFAR-10)**

* **Multi-View Capsules**: silhouette, texture, structure, diffused view.

* **Ensemble Fusion**: calibrated per-view posteriors with perturbation-based stability weighting.

* **Performance**:

  * Best single view: \~0.57–0.61 accuracy.

  * Ensemble capsule: \~0.65 accuracy with only 60 labels per class.

---

## **5\. Technical Advantages**

* **No backpropagation loops** → efficient, CPU-friendly.

* **Few-label efficiency** → competitive results with 30–60 labels per class.

* **Signed Laplacians** → explicit modeling of attraction and repulsion.

* **Interpretability** → eigenvalues, components, and capsule diagnostics are inspectable.

* **Robustness** → multi-view consensus and stability weighting reduce spurious edges.

---

## **6\. Limitations & Future Work**

* Current feature extractors (PCA, HOG, silhouette, texture) are lightweight and may underperform deep CNN embeddings.

* Negative graphs rely on farthest neighbors; alternative dissimilarity measures may improve capsule stability.

* Capsule transfer has been tested only within dataset slices; broader cross-dataset transfer remains open.

* Scalability: performance is CPU-efficient for up to \~10k samples; GPU acceleration may extend further.

---

## **7\. Applications**

* **Semi-supervised classification** with very few labels.

* **Data topology analysis**: inspect manifold geometry via capsule eigenvectors.

* **Interpretable learning**: capsules provide spectral diagnostics.

* **Lightweight edge devices**: inference without heavy model weights.

* **Multi-view data fusion**: capsule ensembles across heterogeneous views.

---

## **8\. Licensing and Availability**

* **License**: MIT License

* **Repository**: (to be linked on GitHub).

* **Dependencies**:

  * Python 3.9+

  * `numpy`, `scipy`, `scikit-learn`, `torchvision`, `scikit-image`

---

## **9\. Release Notes**

* **v1.0** (Initial Release):

  * Implemented CNTC v2 (Consensus Nearest \+ True Capsule).

  * Positive/negative affinities with robust scaling.

  * Signed label propagation with seed-only tuning.

  * Multi-view ensemble capsules with calibration and stability weighting.

  * Benchmarked on Fashion-MNIST, CIFAR-10, and Cat vs Dog subset.

