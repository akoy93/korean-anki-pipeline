import { Moon, SunMedium } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { ThemeMode } from "@/state/theme";

export function ThemeToggle({
  theme,
  onToggle,
}: {
  theme: ThemeMode;
  onToggle: () => void;
}) {
  const darkMode = theme === "dark";

  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      className="gap-2 rounded-full bg-background/80 px-3 backdrop-blur supports-[backdrop-filter]:bg-background/70"
      onClick={onToggle}
      aria-label={darkMode ? "Switch to light mode" : "Switch to dark mode"}
    >
      {darkMode ? (
        <SunMedium className="h-4 w-4" />
      ) : (
        <Moon className="h-4 w-4" />
      )}
      <span className="sm:hidden">{darkMode ? "Light" : "Dark"}</span>
      <span className="hidden sm:inline">
        {darkMode ? "Light mode" : "Dark mode"}
      </span>
    </Button>
  );
}
