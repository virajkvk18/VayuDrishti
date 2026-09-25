import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VayuDRISHTI | Atmospheric Model Diagnostic & High-Impact Uncertainty Engine",
  description:
    "Enterprise-grade diagnostic workspace and explainable AI framework for detecting Numerical Weather Prediction (NWP) model failure modes, bust probabilities, and baroclinic uncertainties over the Indian subcontinent.",
  keywords: [
    "Atmospheric Modeling",
    "NWP Diagnostic",
    "Forecast Bust Risk",
    "Explainable AI",
    "SHAP Meteorology",
    "Operational Weather Telemetry",
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[#090d16] text-slate-100 antialiased selection:bg-sky-500/20 selection:text-sky-200">
        {children}
      </body>
    </html>
  );
}
