import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { persistQueryClient } from "@tanstack/react-query-persist-client";
import { createAsyncStoragePersister } from "@tanstack/query-async-storage-persister";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10 * 60 * 1000,
    },
  },
});

const getMinute = (minute: number) => {
  return minute * 60 * 1000;
};

if (typeof window !== "undefined") {
  const localStoragePersister = createAsyncStoragePersister({
    storage: {
      getItem: async (key) => window.localStorage.getItem(key),
      setItem: async (key, value) => window.localStorage.setItem(key, value),
      removeItem: async (key) => window.localStorage.removeItem(key),
    },
  });

  // The race and event lists come from this bot's own server in a fraction of a
  // second, and the event list alone is 1.5 MB, too much for localStorage. A
  // stored copy also outlives a server restart: an empty answer from a server
  // that predated /data/events came back on every reload for ten minutes.
  // "trainees" is here for the second reason as much as the first: a stored
  // copy from before the list carried portraits kept serving art-less rows for
  // ten minutes after the server started sending them.
  const LOCAL_QUERIES = ["events", "races", "trainees"];

  persistQueryClient({
    queryClient,
    persister: localStoragePersister,
    maxAge: getMinute(10),
    // Bumped to drop caches saved before LOCAL_QUERIES stopped being stored.
    buster: "local-data-2",
    dehydrateOptions: {
      shouldDehydrateQuery: (query) =>
        query.state.status === "success" && !LOCAL_QUERIES.includes(String(query.queryKey[0])),
    },
  });
}

export function QueryProvider({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
