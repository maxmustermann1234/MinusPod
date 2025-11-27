import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { getFeeds, refreshFeed, refreshAllFeeds, deleteFeed } from '../api/feeds';
import FeedCard from '../components/FeedCard';
import LoadingSpinner from '../components/LoadingSpinner';

function Dashboard() {
  const queryClient = useQueryClient();
  const [refreshingSlug, setRefreshingSlug] = useState<string | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  const { data: feeds, isLoading, error } = useQuery({
    queryKey: ['feeds'],
    queryFn: getFeeds,
  });

  const refreshMutation = useMutation({
    mutationFn: refreshFeed,
    onMutate: (slug) => setRefreshingSlug(slug),
    onSettled: () => {
      setRefreshingSlug(null);
      queryClient.invalidateQueries({ queryKey: ['feeds'] });
    },
  });

  const refreshAllMutation = useMutation({
    mutationFn: refreshAllFeeds,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['feeds'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteFeed,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['feeds'] });
      setDeleteConfirm(null);
    },
  });

  const handleDelete = (slug: string) => {
    if (deleteConfirm === slug) {
      deleteMutation.mutate(slug);
    } else {
      setDeleteConfirm(slug);
      setTimeout(() => setDeleteConfirm(null), 3000);
    }
  };

  if (isLoading) {
    return <LoadingSpinner className="py-12" />;
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-destructive">Failed to load feeds</p>
        <p className="text-sm text-muted-foreground mt-2">{(error as Error).message}</p>
      </div>
    );
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-foreground">Feeds</h1>
        <div className="flex gap-2">
          <button
            onClick={() => refreshAllMutation.mutate()}
            disabled={refreshAllMutation.isPending}
            className="px-4 py-2 rounded bg-secondary text-secondary-foreground hover:bg-secondary/80 disabled:opacity-50 transition-colors"
          >
            {refreshAllMutation.isPending ? 'Refreshing...' : 'Refresh All'}
          </button>
          <Link
            to="/add"
            className="px-4 py-2 rounded bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            Add Feed
          </Link>
        </div>
      </div>

      {!feeds || feeds.length === 0 ? (
        <div className="text-center py-12 bg-card rounded-lg border border-border">
          <p className="text-muted-foreground mb-4">No feeds added yet</p>
          <Link
            to="/add"
            className="inline-block px-4 py-2 rounded bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            Add Your First Feed
          </Link>
          <p className="text-sm text-muted-foreground mt-4">
            Find podcast RSS feeds at{' '}
            <a
              href="https://podcastindex.org/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              podcastindex.org
            </a>
          </p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {feeds.map((feed) => (
            <FeedCard
              key={feed.slug}
              feed={feed}
              onRefresh={(slug) => refreshMutation.mutate(slug)}
              onDelete={handleDelete}
              isRefreshing={refreshingSlug === feed.slug}
            />
          ))}
        </div>
      )}

      {deleteConfirm && (
        <div className="fixed bottom-4 right-4 bg-card border border-border rounded-lg p-4 shadow-lg">
          <p className="text-sm text-foreground">Click delete again to confirm</p>
        </div>
      )}
    </div>
  );
}

export default Dashboard;
