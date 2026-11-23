import { Providers } from "@/components/providers";

export default function ProducerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <Providers>{children}</Providers>;
}
