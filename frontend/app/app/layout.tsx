import { AppStatusProvider } from "@/lib/api/AppStatusContext";
import WalletProvider from "@/lib/wallet/WalletProvider";
import AppNav from "./AppNav";
import StatusStrip from "./StatusStrip";
import BackendGate from "./_components/BackendGate";

export default function AppSectionLayout({ children }: { children: React.ReactNode }) {
  return (
    <WalletProvider>
    <AppStatusProvider>
      <div className="app-root">
        <AppNav />
        <StatusStrip />
        <main className="app-main">
          <BackendGate>{children}</BackendGate>
        </main>
      </div>
    </AppStatusProvider>
    </WalletProvider>
  );
}
