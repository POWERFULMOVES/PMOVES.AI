/* ═══════════════════════════════════════════════════════════════════════════
   TensorZero Function Editor Component
   Edit function configurations with variant management
   ═══════════════════════════════════════════════════════════════════════════ */

'use client';

import { useState } from 'react';
import type { FunctionConfig, VariantConfig, ToolConfig } from './types';

interface FunctionEditorProps {
  functions: FunctionConfig[];
  availableProviders: string[];
  onChange: (functions: FunctionConfig[]) => void;
  className?: string;
}

export function FunctionEditor({ functions, availableProviders, onChange, className = '' }: FunctionEditorProps) {
  const [selectedFunction, setSelectedFunction] = useState<number | null>(null);
  const [editingVariant, setEditingVariant] = useState<number | null>(null);

  const selectedFunctionData = selectedFunction !== null ? functions[selectedFunction] : null;

  const addFunction = () => {
    const newFunction: FunctionConfig = {
      name: `function_${functions.length + 1}`,
      description: 'New function description',
      system_prompt: 'You are a helpful AI assistant.',
      variants: [],
    };
    onChange([...functions, newFunction]);
    setSelectedFunction(functions.length);
  };

  const updateFunction = (index: number, updates: Partial<FunctionConfig>) => {
    const updated = [...functions];
    updated[index] = { ...updated[index], ...updates };
    onChange(updated);
  };

  const deleteFunction = (index: number) => {
    const updated = functions.filter((_, i) => i !== index);
    onChange(updated);
    if (selectedFunction === index) {
      setSelectedFunction(null);
    } else if (selectedFunction !== null && selectedFunction > index) {
      setSelectedFunction(selectedFunction - 1);
    }
  };

  const addVariant = (functionIndex: number) => {
    const func = functions[functionIndex];
    const newVariant: VariantConfig = {
      name: `variant_${func.variants.length + 1}`,
      model: 'llama3.2',
      provider: availableProviders[0] || 'ollama',
      temperature: 0.7,
      max_tokens: 2048,
    };
    updateFunction(functionIndex, {
      variants: [...func.variants, newVariant],
    });
  };

  const updateVariant = (functionIndex: number, variantIndex: number, updates: Partial<VariantConfig>) => {
    const func = functions[functionIndex];
    const updatedVariants = [...func.variants];
    updatedVariants[variantIndex] = { ...updatedVariants[variantIndex], ...updates };
    updateFunction(functionIndex, { variants: updatedVariants });
  };

  const deleteVariant = (functionIndex: number, variantIndex: number) => {
    const func = functions[functionIndex];
    updateFunction(functionIndex, {
      variants: func.variants.filter((_, i) => i !== variantIndex),
    });
  };

  return (
    <div className={`card-mech p-6 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="font-display font-bold text-lg uppercase tracking-wide text-cata-violet">
            Function Editor
          </h3>
          <p className="text-sm text-ink-secondary mt-1 font-body">
            Configure functions and their variants
          </p>
        </div>
        <button
          onClick={addFunction}
          className="px-4 py-2 font-pixel text-[7px] uppercase tracking-wider bg-cata-violet text-void hover:bg-cata-violet-dim transition-all"
        >
          Add Function
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Function List */}
        <div className="lg:col-span-1 space-y-2">
          <div className="font-pixel text-[7px] text-ink-muted uppercase mb-3">Functions</div>
          {functions.map((func, idx) => (
            <button
              key={func.name}
              onClick={() => setSelectedFunction(idx)}
              className={`w-full text-left p-4 rounded-lg border transition-all ${
                selectedFunction === idx
                  ? 'bg-cata-violet/10 border-cata-violet'
                  : 'bg-void-soft border-border-subtle hover:border-cata-violet/50'
              }`}
            >
              <div className="font-display font-semibold text-sm uppercase tracking-wide">
                {func.name}
              </div>
              <div className="font-pixel text-[6px] text-ink-muted uppercase mt-1">
                {func.variants.length} {func.variants.length === 1 ? 'variant' : 'variants'}
              </div>
            </button>
          ))}
        </div>

        {/* Function Details */}
        <div className="lg:col-span-2">
          {selectedFunctionData ? (
            <div className="space-y-6">
              {/* Function Metadata */}
              <div className="bg-void-soft rounded-lg p-4 border border-border-subtle">
                <div className="font-pixel text-[7px] text-ink-muted uppercase mb-4">Function Details</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block font-pixel text-[6px] text-ink-muted uppercase mb-2">
                      Function Name
                    </label>
                    <input
                      type="text"
                      value={selectedFunctionData.name}
                      onChange={(e) => updateFunction(selectedFunction!, { name: e.target.value })}
                      className="w-full px-3 py-2 bg-void border border-border-subtle rounded font-mono text-sm text-ink-primary focus:border-cata-violet focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block font-pixel text-[6px] text-ink-muted uppercase mb-2">
                      Description (optional)
                    </label>
                    <input
                      type="text"
                      value={selectedFunctionData.description || ''}
                      onChange={(e) => updateFunction(selectedFunction!, { description: e.target.value })}
                      className="w-full px-3 py-2 bg-void border border-border-subtle rounded font-mono text-sm text-ink-primary focus:border-cata-violet focus:outline-none"
                    />
                  </div>
                </div>
                <div className="mt-4">
                  <label className="block font-pixel text-[6px] text-ink-muted uppercase mb-2">
                    System Prompt
                  </label>
                  <textarea
                    value={selectedFunctionData.system_prompt}
                    onChange={(e) => updateFunction(selectedFunction!, { system_prompt: e.target.value })}
                    rows={4}
                    className="w-full px-3 py-2 bg-void border border-border-subtle rounded font-mono text-sm text-ink-primary focus:border-cata-violet focus:outline-none resize-none"
                  />
                </div>
                <div className="mt-4 flex justify-end">
                  <button
                    onClick={() => deleteFunction(selectedFunction!)}
                    className="px-4 py-2 font-pixel text-[7px] uppercase tracking-wider bg-cata-ember text-void hover:bg-cata-ember-dim transition-all"
                  >
                    Delete Function
                  </button>
                </div>
              </div>

              {/* Variants */}
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div className="font-pixel text-[7px] text-ink-muted uppercase">Variants</div>
                  <button
                    onClick={() => addVariant(selectedFunction!)}
                    className="px-3 py-1.5 font-pixel text-[6px] uppercase tracking-wider bg-void-soft text-ink-secondary hover:text-cata-cyan border border-border-subtle hover:border-cata-cyan transition-all"
                  >
                    Add Variant
                  </button>
                </div>

                <div className="space-y-3">
                  {selectedFunctionData.variants.map((variant, vIdx) => (
                    <div
                      key={variant.name}
                      className="bg-void-soft rounded-lg p-4 border border-border-subtle"
                    >
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                          <label className="block font-pixel text-[6px] text-ink-muted uppercase mb-2">
                            Variant Name
                          </label>
                          <input
                            type="text"
                            value={variant.name}
                            onChange={(e) => updateVariant(selectedFunction!, vIdx, { name: e.target.value })}
                            className="w-full px-3 py-2 bg-void border border-border-subtle rounded font-mono text-xs text-ink-primary focus:border-cata-cyan focus:outline-none"
                          />
                        </div>
                        <div>
                          <label className="block font-pixel text-[6px] text-ink-muted uppercase mb-2">
                            Model
                          </label>
                          <input
                            type="text"
                            value={variant.model}
                            onChange={(e) => updateVariant(selectedFunction!, vIdx, { model: e.target.value })}
                            className="w-full px-3 py-2 bg-void border border-border-subtle rounded font-mono text-xs text-ink-primary focus:border-cata-cyan focus:outline-none"
                          />
                        </div>
                        <div>
                          <label className="block font-pixel text-[6px] text-ink-muted uppercase mb-2">
                            Provider
                          </label>
                          <select
                            value={variant.provider}
                            onChange={(e) => updateVariant(selectedFunction!, vIdx, { provider: e.target.value })}
                            className="w-full px-3 py-2 bg-void border border-border-subtle rounded font-mono text-xs text-ink-primary focus:border-cata-cyan focus:outline-none"
                          >
                            {availableProviders.map((provider) => (
                              <option key={provider} value={provider}>
                                {provider}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className="block font-pixel text-[6px] text-ink-muted uppercase mb-2">
                            Temperature: {variant.temperature || 0.7}
                          </label>
                          <input
                            type="range"
                            min="0"
                            max="2"
                            step="0.1"
                            value={variant.temperature || 0.7}
                            onChange={(e) => updateVariant(selectedFunction!, vIdx, { temperature: parseFloat(e.target.value) })}
                            className="w-full"
                          />
                        </div>
                        <div>
                          <label className="block font-pixel text-[6px] text-ink-muted uppercase mb-2">
                            Max Tokens
                          </label>
                          <input
                            type="number"
                            value={variant.max_tokens || 2048}
                            onChange={(e) => updateVariant(selectedFunction!, vIdx, { max_tokens: parseInt(e.target.value) })}
                            className="w-full px-3 py-2 bg-void border border-border-subtle rounded font-mono text-xs text-ink-primary focus:border-cata-cyan focus:outline-none"
                          />
                        </div>
                      </div>
                      <div className="mt-3 flex justify-end">
                        <button
                          onClick={() => deleteVariant(selectedFunction!, vIdx)}
                          className="px-3 py-1.5 font-pixel text-[6px] uppercase tracking-wider bg-cata-ember text-void hover:bg-cata-ember-dim transition-all"
                        >
                          Remove
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-void-soft rounded-lg p-8 border border-border-subtle text-center">
              <div className="text-ink-muted font-pixel text-[7px] uppercase mb-2">
                No function selected
              </div>
              <div className="text-sm text-ink-secondary font-body">
                Select a function from the list to edit its configuration
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
