'use client'

import { useEffect, useState } from "react";

export default function ClientWrapper({
  children,
}: {
  children: React.ReactNode;
}) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <div className="min-h-screen overflow-auto">
        <div style={{ visibility: 'hidden' }}>
          {children}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen overflow-auto">
      {children}
    </div>
  );
} 