import { useRef } from "react";
import { validateConfig } from "../utils/validateConfig";
import { URL } from "../constants";
import type { Config } from "../types";

type Props = {
  config: Config;
  setConfig: (config: Config) => void;
};

// Fills keys an older config file lacks (a section added since) from the
// config on screen, so loading one doesn't fail validation.
const deepMerge = <T extends object>(target: T, source: T): T => {
  const output = {} as T;

  for (const key in source) {
    if (
      source[key] &&
      typeof source[key] === "object" &&
      !Array.isArray(source[key])
    ) {
      output[key] = deepMerge(
        (target[key] as object) ?? {},
        source[key] as object
      ) as T[Extract<keyof T, string>];
    } else {
      output[key] = target[key] !== undefined ? target[key] : source[key];
    }
  }

  return output;
};

export function useImportConfig({ config, setConfig }: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const openFileDialog = () => {
    fileInputRef.current?.click();
  };

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      const text = await file.text();
      const json = deepMerge(JSON.parse(text), config);

      const result = validateConfig(json);

      if (!result.success) {
        console.error("Invalid config:", result.errors);
        alert(JSON.stringify(result.errors, null, 2));
        return;
      }

      setConfig(json);

      try {
        await fetch(`${URL}/config`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(json),
        });
      } catch (err) {
        console.warn("Failed to sync with server:", err);
      }

      alert(`Loaded ${file.name}`);
    } catch (err) {
      console.error("Import error:", err);
      alert("Failed to load config");
    } finally {
      e.target.value = "";
    }
  };

  return {
    fileInputRef,
    openFileDialog,
    handleImport,
  };
}
