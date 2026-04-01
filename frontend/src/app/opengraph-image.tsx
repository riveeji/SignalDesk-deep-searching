import { ImageResponse } from "next/og";

import { APP_BLURB, APP_LINE, APP_NAME, APP_NAME_CN } from "@/lib/brand";

export const size = {
  width: 1200,
  height: 630,
};

export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          position: "relative",
          background:
            "radial-gradient(circle at top left, rgba(255,213,143,0.22), transparent 28%), radial-gradient(circle at bottom right, rgba(127,212,255,0.2), transparent 34%), linear-gradient(180deg, #090b12 0%, #0f1220 42%, #111527 100%)",
          color: "#f7f4ef",
          padding: "56px",
          fontFamily: "sans-serif",
        }}
      >
        <div
          style={{
            position: "absolute",
            inset: 0,
            opacity: 0.08,
            backgroundImage:
              "linear-gradient(rgba(255,255,255,0.16) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.16) 1px, transparent 1px)",
            backgroundSize: "52px 52px",
          }}
        />
        <div
          style={{
            display: "flex",
            width: "100%",
            border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: 36,
            background: "rgba(16,19,31,0.82)",
            padding: "42px 44px",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", maxWidth: 760 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
              <div
                style={{
                  width: 72,
                  height: 72,
                  borderRadius: 24,
                  border: "1px solid rgba(255,255,255,0.1)",
                  background:
                    "radial-gradient(circle at top left, rgba(255,213,143,0.22), transparent 34%), radial-gradient(circle at bottom right, rgba(127,212,255,0.2), transparent 34%), linear-gradient(180deg, rgba(18,21,33,0.96), rgba(9,11,18,1))",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <div
                  style={{
                    width: 34,
                    height: 34,
                    borderRadius: 12,
                    border: "2px solid #FFD58F",
                    transform: "rotate(45deg)",
                    boxShadow: "0 0 0 2px rgba(127,212,255,0.18) inset",
                  }}
                />
              </div>
              <div style={{ display: "flex", flexDirection: "column" }}>
                <span style={{ fontSize: 18, letterSpacing: 6, textTransform: "uppercase", color: "#f4d8a1" }}>
                  {APP_NAME_CN}
                </span>
                <span style={{ marginTop: 8, fontSize: 44, fontWeight: 700 }}>{APP_NAME}</span>
              </div>
            </div>
            <div style={{ display: "flex", marginTop: 40, fontSize: 66, lineHeight: 1.08, fontWeight: 700 }}>
              {APP_LINE}
            </div>
            <div style={{ display: "flex", marginTop: 24, fontSize: 28, lineHeight: 1.5, color: "#b8bcc9" }}>
              {APP_BLURB}
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", width: 260, gap: 16 }}>
            {[
              "直接搜索问题",
              "多模型后端切换",
              "证据追踪与回放",
              "引用驱动报告",
            ].map((item) => (
              <div
                key={item}
                style={{
                  display: "flex",
                  padding: "16px 18px",
                  borderRadius: 20,
                  border: "1px solid rgba(255,255,255,0.1)",
                  background: "rgba(255,255,255,0.04)",
                  fontSize: 22,
                }}
              >
                {item}
              </div>
            ))}
          </div>
        </div>
      </div>
    ),
    size,
  );
}
