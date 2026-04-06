import { useSettingsContext } from "../providers/SettingsProvider";

export function useSettings() {
  return useSettingsContext();
}
