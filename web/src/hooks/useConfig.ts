import { useEffect, useState } from "react";
import { URL } from "../constants";
import type { Config } from "../types";

export function useConfig(defaultConfig: Config) {
  const [config, setConfig] = useState<Config>(defaultConfig);

  useEffect(() => {
    const getConfig = async () => {
      try {
        const res = await fetch(`${URL}/config`);
        const data = await res.json();
        setConfig(data);
      } catch (error) {
        console.log(error);
      }
    };
    getConfig();
  }, []);

  const saveConfig = async () => {
    try {
      const res = await fetch(`${URL}/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });

      if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);

      const data = await res.json();
      console.log("Saved config:", data);
      alert("Config applied!");
    } catch (error) {
      console.log(error);
    }
  };

  return { config, setConfig, saveConfig };
}
