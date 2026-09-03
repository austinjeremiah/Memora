import { AppStatusProvider } from "@/lib/api/AppStatusContext";
import AppNav from "./AppNav";
import StatusStrip from "./StatusStrip";
import BackendGate from "./_components/BackendGate";

export default function AppSectionLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppStatusProvider>
      <div
        style={{
          minHeight: "100vh",
          background: "#050608",
          color: "#fff",
          fontFamily: "sans-serif",
        }}
      >
        <AppNav />
        <StatusStrip />
        <main style={{ padding: "24px 20px", maxWidth: "960px", margin: "0 auto" }}>
          <BackendGate>{children}</BackendGate>
        </main>
      </div>
    </AppStatusProvider>
  );
}
