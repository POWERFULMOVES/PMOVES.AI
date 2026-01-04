import { defineConfig, globalIgnores } from 'eslint/config';
import nextVitals from 'eslint-config-next/core-web-vitals';
import nextTs from 'eslint-config-next/typescript';

const customRules = defineConfig({
  files: ['**/*.{ts,tsx,js,jsx}'],
  rules: {
    '@typescript-eslint/no-explicit-any': 'off',
   '@typescript-eslint/no-unused-vars': [
     'warn',
      {
        argsIgnorePattern: '^_',
        varsIgnorePattern: '^_',
        caughtErrorsIgnorePattern: '^_'
      }
    ],
    '@typescript-eslint/no-require-imports': 'off',
  },
});

export default defineConfig([
  ...nextVitals,
  ...nextTs,
  customRules,
  globalIgnores([
    '.next/**',
    'out/**',
    'build/**',
    'next-env.d.ts',
  ]),
]);
