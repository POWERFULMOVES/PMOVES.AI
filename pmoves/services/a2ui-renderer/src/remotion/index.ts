/**
 * Remotion Entry Point — A2UI Composition Registry
 *
 * Registers all available compositions for the A2UI renderer.
 * The bundler uses this file as the entry point.
 */

import { registerRoot } from 'remotion';
import { A2UIComposition } from './A2UIComposition';

const RemotionRoot: React.FC = () => {
  return <A2UIComposition />;
};

registerRoot(RemotionRoot);
