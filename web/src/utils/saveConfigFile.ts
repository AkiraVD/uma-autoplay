import type { Config } from "../types";

type SaveFilePicker = (options: {
  suggestedName: string;
  types: { description: string; accept: Record<string, string[]> }[];
}) => Promise<{
  createWritable: () => Promise<{
    write: (data: string) => Promise<void>;
    close: () => Promise<void>;
  }>;
}>;

// "Mihono Bourbon - Grand Concert" -> "config.mihono-bourbon-grand-concert.json",
// the same shape as the config.*.json files kept next to config.json.
const suggestedName = (config: Config) => {
  const slug = (config.config_name || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return `config.${slug || "export"}.json`;
};

export async function saveConfigFile(config: Config) {
  const text = JSON.stringify(config, null, 2);
  const name = suggestedName(config);
  const picker = (window as unknown as { showSaveFilePicker?: SaveFilePicker })
    .showSaveFilePicker;

  // Chrome/Edge: a real save dialog, so the file can go straight into the bot's folder.
  if (picker) {
    try {
      const handle = await picker({
        suggestedName: name,
        types: [{ description: "Config", accept: { "application/json": [".json"] } }],
      });
      const writable = await handle.createWritable();
      await writable.write(text);
      await writable.close();
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        console.error("Save error:", err);
        alert("Failed to save config file");
      }
    }
    return;
  }

  // Other browsers: a plain download.
  const url = window.URL.createObjectURL(new Blob([text], { type: "application/json" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  window.URL.revokeObjectURL(url);
}
