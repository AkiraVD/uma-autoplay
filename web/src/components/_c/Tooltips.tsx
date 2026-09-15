import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { CircleQuestionMarkIcon } from "lucide-react";

type Props = {
  children: React.ReactNode;
};

export default function Tooltips({ children }: Props) {
  return (
    <Tooltip>
      <TooltipTrigger>
        <CircleQuestionMarkIcon size={20} />
      </TooltipTrigger>
      {/* Without a cap a long tooltip lays itself out as one line and runs off
          the side of the page instead of wrapping. */}
      <TooltipContent className="max-w-xs text-wrap">{children}</TooltipContent>
    </Tooltip>
  );
}
