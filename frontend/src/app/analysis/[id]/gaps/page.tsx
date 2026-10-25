"use client";

import { useEffect, use } from "react";
import { useRouter } from "next/navigation";

export default function GapsRedirect({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();

  useEffect(() => {
    router.replace(`/analysis/${id}`);
  }, [id, router]);

  return (
    <div className="p-8 text-center text-xs text-[#8b949e]">
      Redirecting to Research-Gap Canvas...
    </div>
  );
}
