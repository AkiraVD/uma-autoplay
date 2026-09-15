import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "../ui/dialog";
import { Button } from "../ui/button";
import EventCard from "./_c/EventCard";
import type { EventChoicesType, EventData, EventType } from "@/types/eventType";
import { Badge } from "../ui/badge";
import { Search, Trash2 } from "lucide-react";
import { Input } from "../ui/input";
import { useMemo, useState } from "react";

type Props = {
  data: EventData | null;
  groupedChoices: EventType[];
  eventChoicesConfig: EventChoicesType[];
  addEventList: (event: EventChoicesType) => void;
  deleteEventList: (event_name: string) => void;
  clearEventList: () => void;
};

export default function SelectedEventList({ data, groupedChoices, eventChoicesConfig, addEventList, deleteEventList, clearEventList }: Props) {
  const [search, setSearch] = useState<string>("");
  const [open, setOpen] = useState<boolean>(false);

  const selectedEvents = groupedChoices?.filter((event) => eventChoicesConfig.some((conf) => conf.event_name === event.event_name));

  // Who the selected events belong to, for the filter list.
  const owners = [
    ...new Set(
      selectedEvents.flatMap((event) =>
        event.character_name.split(",").map((name) => name.trim()).filter((name) => name !== "")
      )
    ),
  ].sort();

  // Configured choices the event data has no entry for. Only meaningful once the data has loaded.
  const unmatched = data
    ? eventChoicesConfig.filter((conf) => !groupedChoices.some((event) => event.event_name === conf.event_name))
    : [];

  const filtered = useMemo(() => {
    const val = search.toLowerCase().toLowerCase();
    return selectedEvents?.filter((ev) => ev.event_name.toLowerCase().includes(val) || ev.character_name.toLowerCase().includes(val));
  }, [selectedEvents, search]);

  const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => setSearch(e.target.value);

  return (
    <Dialog
      open={open}
      onOpenChange={(open) => {
        setOpen(open);
        setSearch("");
      }}
    >
      <DialogTrigger asChild>
        <Button variant="outline" className="w-full flex items-center gap-2">
          Selected Events
          {eventChoicesConfig.length > 0 && (
            <Badge variant="secondary" className="ml-1 text-xs px-2">
              {eventChoicesConfig.length}
            </Badge>
          )}
        </Button>
      </DialogTrigger>

      <DialogContent className="h-[85vh] w-full max-w-[90vw] p-0 overflow-hidden [&>button]:hidden">
        {/* Header */}
        <DialogHeader className="p-4 border-b flex flex-row items-center justify-between bg-muted/40">
          <DialogTitle className="text-lg font-semibold">Selected Events</DialogTitle>

          {eventChoicesConfig.length > 0 && (
            <Button variant="destructive" size="sm" onClick={clearEventList} className="flex items-center gap-1">
              <Trash2 className="w-4 h-4" /> Clear All Events
            </Button>
          )}
        </DialogHeader>

        <div className="flex h-[75vh]">
          {/* LEFT SIDE */}
          <div className="border-r p-4 flex flex-col gap-4">
            <div className="relative">
              <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <Input type="search" placeholder="Search events or characters..." value={search} onChange={handleSearch} className="pl-10" />
            </div>

            <div className="overflow-y-auto px-2">
              <p className="text-sm font-medium mb-2 text-muted-foreground">Filter</p>
              <div className="flex flex-col gap-1 w-56">
                {owners.map((owner) => (
                  <button
                    key={owner}
                    onClick={() => setSearch(search === owner ? "" : owner)}
                    className={`text-left text-sm px-2 py-1 rounded-md hover:bg-accent transition ${search === owner ? "bg-accent font-medium" : ""}`}
                  >
                    {owner}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* RIGHT SIDE */}
          <div className="flex-1 overflow-y-auto p-4">
            {filtered?.length > 0 || unmatched.length > 0 ? (
              <div className="flex flex-col gap-4">
                {filtered.map((event) => (
                  <EventCard key={event.event_name} addEventList={addEventList} event={event} eventChoicesConfig={eventChoicesConfig} deleteEventList={deleteEventList} />
                ))}
                {unmatched.length > 0 && (
                  <div className="rounded-lg border border-dashed p-4">
                    <p className="font-medium">Not in the current event list ({unmatched.length})</p>
                    <p className="text-sm text-muted-foreground mb-3">
                      Saved under a name the event data doesn't use (often an old grade split like "(G2)"). The bot still
                      matches these by name; re-pick the event from the Event List to see its outcomes, or remove it.
                    </p>
                    <div className="flex flex-col gap-1.5">
                      {unmatched.map((ev) => (
                        <div key={ev.event_name} className="flex items-center gap-2 text-sm rounded-md border bg-background px-3 py-1.5">
                          <span className="flex-1 min-w-0 truncate">{ev.event_name}</span>
                          <span className="text-muted-foreground shrink-0">Choice {ev.chosen}</span>
                          <button
                            type="button"
                            aria-label={`Remove ${ev.event_name}`}
                            onClick={() => deleteEventList(ev.event_name)}
                            className="p-1 text-muted-foreground hover:text-destructive"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-center text-muted-foreground">
                <p className="text-base font-medium">No events selected yet</p>
                <p className="text-sm">Select some from the list to see them here</p>
              </div>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
