import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { DocumentsTable } from "../../components/DocumentsTable";
import { ErrorState } from "../../components/ErrorState";
import { api } from "../api";

type TableProps = Parameters<typeof DocumentsTable>[0];

export default function Documents() {
  const { slug } = useParams();
  const queryClient = useQueryClient();
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["documents-table", slug],
    queryFn: () => api<TableProps>(`/projects/${slug}/documents-table/`),
  });

  if (isLoading) return <p className="text-sm text-stone-400 dark:text-stone-500">Loading documents…</p>;
  if (error || !data) return <ErrorState message="Couldn't load documents." onRetry={() => refetch()} />;

  return (
    <div>
      <nav className="mb-6 text-sm text-stone-500">
        <Link to="/projects" className="hover:underline">Projects</Link> /{" "}
        <Link to={`/projects/${slug}`} className="hover:underline">{slug}</Link> / Documents
      </nav>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Documents</h1>
        <div className="flex items-center gap-4 text-xs">
          <Link to={`/projects/${slug}/figures`}
                className="font-medium text-indigo-600 hover:underline">
            View as gallery →
          </Link>
          <a href={`/projects/${slug}/documents/`}
             className="text-stone-400 underline hover:text-indigo-700">
            folders & upload on the classic page ↗
          </a>
        </div>
      </div>
      <DocumentsTable
        {...data}
        onDone={() => queryClient.invalidateQueries({ queryKey: ["documents-table", slug] })}
      />
    </div>
  );
}
