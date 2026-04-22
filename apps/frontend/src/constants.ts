/** Delay applied to text-search inputs before triggering a fetch.
 *  Tuned for HA instances with thousands of entities — most users finish
 *  typing before 250 ms. Lower this if typing ever feels laggy. */
export const SEARCH_DEBOUNCE_MS = 250;
