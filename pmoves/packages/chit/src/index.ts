/**
 * @pmoves/chit — Workspace Package
 *
 * Thread 3.1: Packages the CHIT TypeScript modules from
 * PMOVES-ToKenism-Multi/integrations/contracts/chit/ as a workspace-level
 * importable package.
 *
 * Modules:
 * - dirichlet-weights:  Probabilistic contribution attribution
 * - hyperbolic-encoder: Poincaré disk geometry encoding
 * - shape-attribution:  Merkle proofs and record tracking
 * - cgp-generator:      CHIT Geometry Packet v2 generation
 * - swarm-attribution:  EVO SWARM fitness-weighted optimization
 * - zeta-filter:        Spectral analysis (Riemann zeta zeros)
 * - chit-nats-publisher: GEOMETRY BUS NATS publishing
 *
 * @packageDocumentation
 */

// Re-export everything from the canonical CHIT source
// The source modules live in the ToKenism-Multi submodule.
// This package provides a clean workspace import path: @pmoves/chit

export {
  // Dirichlet Weights
  DirichletWeights,
  type DirichletConfig,
  type ContributionWeight,
  type CategoryContributions,
  type AttributionExport,

  // Hyperbolic Encoder
  HyperbolicEncoder,
  type EncoderConfig,
  type PoincarePoint,
  type HierarchyNode,
  type CGPSuperNode,
  type CGPConstellation,
  type CGPPoint,

  // Shape Attribution
  ShapeAttribution,
  type ShapeAttributionConfig,
  type MerkleConfig,
  type MerkleTreeStrategy,
  type AttributionRecord,
  type AttributionAction,
  type AttributionProof,

  // CGP Generator
  CGPGenerator,
  type CGPGeneratorConfig,
  type CGPDocument,
  type CGPSuperNodeExtended,
  type CGPAttribution,
  type CGPContributor,
  type CGPMerkleProof,
  type CGPHyperbolicEncoding,
  type CGPPoincarePoint,
  type CGPSignature,
  type WeeklySimulationData,
  type TransactionRecord,
  type ToKenismModality,
  type ContractType,

  // Swarm Attribution
  SwarmAttribution,
  type SwarmAttributionConfig,
  type SwarmMeta,
  type ToKenismMetrics,
  type OptimizationTarget,
  type FitnessWeights,
  type Population,
  type GenerationRecord,

  // Zeta Filter
  ZetaInspiredFilter,
  type ZetaFilterConfig,
  type SpectralAnalysis,

  // NATS Publisher
  CHITNATSPublisher,
  createCHITPublisher,
  type SwarmPopulationPayload,
  type AttributionRecordedPayload,
  type CGPWeeklyPayload,

  // Factory & Constants
  createCHITSystem,
  type CHITSystem,
  type CHITSystemConfig,
  CHIT_VERSION,
  CHIT_NATS_SUBJECTS,
  validateCGPDocument,
  validateCGPArchive,

  // Credential types
  type CHITRedactionRecord,
  type CredentialRotationEvent,
} from '../../../PMOVES-ToKenism-Multi/integrations/contracts/chit/index';
