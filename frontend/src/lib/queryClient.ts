import { QueryClient } from "@tanstack/react-query"

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5,   // 5 minutes
      retry: (failureCount, error: any) => {
        // Don't retry on 401 (auth), 403 (forbidden), 404 (not found)
        if ([401, 403, 404].includes(error?.status)) return false
        return failureCount < 2
      },
    },
  },
})
