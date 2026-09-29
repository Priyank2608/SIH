import type { Metadata, Viewport } from 'next';
import './globals.css';
import AppShellWrapper from '../components/AppShellWrapper';

export const metadata: Metadata = {
  title: 'BidShield — Procurement Review Console',
  description:
    'Evidence-backed review console for Government e-Marketplace bid verification. Authorized procurement, verification, and audit personnel only.',
  icons: {
    icon: [
      { url: '/icon.svg', type: 'image/svg+xml' },
    ],
  },
};

export const viewport: Viewport = {
  themeColor: '#0b111c',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <AppShellWrapper>
          {children}
        </AppShellWrapper>
      </body>
    </html>
  );
}
