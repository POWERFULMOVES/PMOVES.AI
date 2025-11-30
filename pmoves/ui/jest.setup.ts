import "@testing-library/jest-dom";

declare global {
  // React 19 expects this flag in test environments to silence act() warnings.
  var IS_REACT_ACT_ENVIRONMENT: boolean | undefined;
}

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
