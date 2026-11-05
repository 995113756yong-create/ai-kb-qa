import ChatApp from "@/components/ChatApp";

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ agent?: string; c?: string }>;
}) {
  const params = await searchParams;
  return (
    <ChatApp initialAgentId={params.agent ?? "default"} initialConversationId={params.c ?? null} />
  );
}
