type StarConfig = {
  id: string;
  top: string;
  left: string;
  size: number;
  delay: string;
  duration: string;
  tone: "neutral" | "warm" | "cool";
  opacity: number;
};

type NebulaConfig = {
  id: string;
  className: string;
  style: {
    top: string;
    left: string;
    width: string;
    height: string;
    background: string;
    animationDelay: string;
    animationDuration: string;
  };
};

const STARS: StarConfig[] = Array.from({ length: 42 }, (_, index) => {
  const top = ((index * 17) % 100) + (index % 3) * 1.2;
  const left = ((index * 29) % 100) + (index % 4) * 0.8;
  const size = 1.2 + (index % 5) * 0.5;
  const delay = `${(index % 9) * 0.55}s`;
  const duration = `${4.2 + (index % 7) * 0.9}s`;
  const tone = index % 7 === 0 ? "cool" : index % 5 === 0 ? "warm" : "neutral";

  return {
    id: `star-${index}`,
    top: `${Math.min(top, 96)}%`,
    left: `${Math.min(left, 97)}%`,
    size,
    delay,
    duration,
    tone,
    opacity: 0.24 + (index % 5) * 0.12,
  };
});

const NEBULAS: NebulaConfig[] = [
  {
    id: "nebula-a",
    className: "starfield-nebula",
    style: {
      top: "-10%",
      left: "-4%",
      width: "32rem",
      height: "32rem",
      background: "radial-gradient(circle, rgba(127,212,255,0.18) 0%, rgba(127,212,255,0.05) 42%, transparent 72%)",
      animationDelay: "0s",
      animationDuration: "26s",
    },
  },
  {
    id: "nebula-b",
    className: "starfield-nebula",
    style: {
      top: "14%",
      left: "68%",
      width: "24rem",
      height: "24rem",
      background: "radial-gradient(circle, rgba(255,213,143,0.16) 0%, rgba(255,213,143,0.04) 40%, transparent 72%)",
      animationDelay: "4s",
      animationDuration: "24s",
    },
  },
  {
    id: "nebula-c",
    className: "starfield-nebula",
    style: {
      top: "66%",
      left: "18%",
      width: "26rem",
      height: "26rem",
      background: "radial-gradient(circle, rgba(196,224,255,0.12) 0%, rgba(196,224,255,0.04) 42%, transparent 72%)",
      animationDelay: "2s",
      animationDuration: "30s",
    },
  },
];

const METEORS = [
  { id: "meteor-1", top: "16%", left: "78%", delay: "1.8s" },
  { id: "meteor-2", top: "36%", left: "88%", delay: "5.6s" },
  { id: "meteor-3", top: "58%", left: "74%", delay: "8.4s" },
];

export function StarfieldBackdrop() {
  return (
    <div aria-hidden="true" className="starfield-shell">
      {NEBULAS.map((nebula) => (
        <span key={nebula.id} className={nebula.className} style={nebula.style} />
      ))}

      <div className="starfield-plane">
        {STARS.map((star) => (
          <span
            key={star.id}
            className="starfield-star"
            data-tone={star.tone}
            style={{
              top: star.top,
              left: star.left,
              width: `${star.size}px`,
              height: `${star.size}px`,
              opacity: star.opacity,
              animationDelay: star.delay,
              animationDuration: star.duration,
            }}
          />
        ))}
      </div>

      {METEORS.map((meteor) => (
        <span
          key={meteor.id}
          className="starfield-meteor"
          style={{
            top: meteor.top,
            left: meteor.left,
            animationDelay: meteor.delay,
          }}
        />
      ))}
    </div>
  );
}
