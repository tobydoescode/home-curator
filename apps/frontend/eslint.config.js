import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

/**
 * The rules TypeScript cannot enforce.
 *
 * `tsc --noEmit` already covers types, unused locals and unused parameters, so
 * this deliberately does not duplicate that. What it adds is the hook rules:
 * nothing else catches a `useEffect` with a wrong dependency array, and this
 * codebase has effects that call `setState` with that same state in their
 * dependencies — correct today only because of a manual guard.
 */
export default tseslint.config(
  {
    ignores: [
      "dist",
      "coverage",
      // Generated from the backend's OpenAPI schema.
      "src/api/generated.ts",
      // Compiled artifacts of `tsc -b`; both are gitignored, and linting the
      // emitted JS reports Node globals as undefined.
      "vite.config.js",
      "vite.config.d.ts",
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": [
        "warn",
        { allowConstantExport: true },
      ],
      // tsc already reports these, and its messages are better.
      "@typescript-eslint/no-unused-vars": "off",
      // Pre-existing "copy props into state" effects, mostly drawers seeding
      // a form from the row they were opened on. Each is guarded and behaves
      // correctly; converting them to keyed remounts or derived state is a
      // behavioural change, not a lint fix, so this warns rather than blocks.
      "react-hooks/set-state-in-effect": "warn",
    },
  },
  {
    // CommonJS build config, not part of the app bundle.
    files: ["**/*.cjs"],
    languageOptions: { globals: globals.node, sourceType: "commonjs" },
  },
  {
    // Tests reach into internals and stub globals on purpose.
    files: ["**/*.test.{ts,tsx}", "tests/**"],
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
    },
  },
);
