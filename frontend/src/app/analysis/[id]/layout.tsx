import React from "react";

export default function AnalysisLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-[#090a0c] text-[#f0f3f6] flex flex-col">
      {children}
    </div>
  );
}
