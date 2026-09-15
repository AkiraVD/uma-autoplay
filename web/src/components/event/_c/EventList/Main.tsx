import type { EventChoicesType, EventType } from "@/types/eventType";
import EventCard from "../EventCard";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Filter } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useEffect, useMemo, useState } from "react";

type Props = {
  eventSelected: EventType[];
  selected: string;
  setSelected: React.Dispatch<React.SetStateAction<string>>;
  eventChoicesConfig: EventChoicesType[];
  addEventList: (event: EventChoicesType) => void;
  deleteEventList: (eventName: string) => void;
};

export default function MainEventList({ eventSelected, selected, setSelected, eventChoicesConfig, addEventList, deleteEventList }: Props) {
  const [search, setSearch] = useState<string>("");

  const filtered = useMemo(() => {
    const val = search.toLowerCase().trim();
    // Unfiltered and unsearched is every event there is: show the prompt instead.
    if (!selected && val === "") return [];
    return eventSelected.filter((ev) => ev.event_name.toLowerCase().includes(val) || ev.character_name.toLowerCase().includes(val));
  }, [eventSelected, search, selected]);
  const SHOWN = 100;
  const shown = filtered.slice(0, SHOWN);

  useEffect(() => {
    setSearch("");
  }, [selected]);

  const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearch(e.target.value);
  };

  return (
    <div className="flex-1 overflow-y-auto p-6 bg-background">
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold">{selected ? `Events for: ${selected}` : "All Events"}</h3>
          <Badge variant="outline" className="text-xs">
            {filtered.length} events found
          </Badge>
        </div>
        <Input value={search} onChange={handleSearch} placeholder="Search events..." />

        <div className="space-y-4">
          {filtered.length > 0 ? (
            <>
              {shown.map((event) => <EventCard addEventList={addEventList} event={event} eventChoicesConfig={eventChoicesConfig} deleteEventList={deleteEventList} key={event.event_name} />)}
              {filtered.length > SHOWN && (
                <p className="text-sm text-muted-foreground text-center">
                  Showing the first {SHOWN} of {filtered.length}. Narrow the search or pick a filter.
                </p>
              )}
            </>
          ) : (
            <Card className="border-dashed">
              <CardContent className="py-12 text-center text-muted-foreground">
                <Filter className="w-12 h-12 mx-auto mb-3 opacity-50" />
                {selected ? (
                  <>
                    <p className="font-medium mb-1">No events found for this filter.</p>
                    <Button variant="outline" size="sm" onClick={() => setSelected("")}>
                      Clear Filter
                    </Button>
                  </>
                ) : search.trim() ? (
                  <p>No event matches "{search.trim()}".</p>
                ) : (
                  <p>Search for an event, or pick a scenario, character, or support card from the sidebar.</p>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
