import { Monitor, Moon, Sun } from "lucide-react";

import { useTheme, type Theme } from "../hooks/useTheme";
import { Button } from "./ui/button";

const NEXT: Record<Theme, Theme> = { light: "dark", dark: "system", system: "light" };
const LABEL: Record<Theme, string> = { light: "Light", dark: "Dark", system: "System" };
const ICON = { light: Sun, dark: Moon, system: Monitor };

export default function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const Icon = ICON[theme];
  const next = NEXT[theme];

  return (
    <Button
      size="sm"
      variant="outline"
      onClick={() => setTheme(next)}
      title={`Theme: ${LABEL[theme]}. Click for ${LABEL[next]}.`}
      aria-label={`Theme: ${LABEL[theme]}. Switch to ${LABEL[next]}.`}
    >
      <Icon className="size-4" />
      <span className="hidden sm:inline">{LABEL[theme]}</span>
    </Button>
  );
}
