// Fixed, decorative warm shapes behind the page so the frosted-glass panels have
// something to blur. Purely visual: hidden from assistive tech and never clickable.
export function Backdrop() {
  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div className="backdrop-orb" style={{ width: "42rem", height: "42rem", left: "-14rem", top: "-16rem", background: "var(--orb-1)" }} />
      <div className="backdrop-orb" style={{ width: "36rem", height: "36rem", right: "-12rem", top: "-10rem", background: "var(--orb-2)" }} />
      <div className="backdrop-orb" style={{ width: "40rem", height: "40rem", right: "-10rem", bottom: "-18rem", background: "var(--orb-3)" }} />
      <div className="backdrop-fan" style={{ width: "46rem", height: "46rem", left: "-20rem", bottom: "-22rem" }} />
      <div className="backdrop-fan" style={{ width: "30rem", height: "30rem", right: "-12rem", top: "-12rem" }} />
    </div>
  );
}
