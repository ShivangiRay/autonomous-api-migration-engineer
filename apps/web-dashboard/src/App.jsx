import React from "react";
import { createRoot } from "react-dom/client";
import { GitCompare, Network, ShieldCheck } from "lucide-react";
import "./styles.css";

const metrics = [
  ["Total endpoints", "5"],
  ["gRPC candidates", "2"],
  ["Event candidates", "1"],
  ["REST retained", "1"],
  ["Breaking risks", "1"],
  ["Readiness score", "87"]
];

function App() {
  return (
    <main className="shell">
      <header>
        <div>
          <p className="eyebrow">Autonomous API Migration Engineer</p>
          <h1>Service Overview</h1>
        </div>
        <button>demo@example.com</button>
      </header>
      <section className="metrics">{metrics.map(([label, value]) => <article key={label}><span>{label}</span><strong>{value}</strong></article>)}</section>
      <section className="grid">
        <article>
          <h2><Network size={18} /> Migration Graph</h2>
          <div className="graph">REST inventory -> gRPC contracts -> compatibility validation -> report approval</div>
        </article>
        <article>
          <h2><GitCompare size={18} /> Contract Diff Viewer</h2>
          <pre>- REST POST /users{"\n"}+ rpc CreateUser(CreateUserRequest) returns (CreateUserResponse)</pre>
        </article>
        <article>
          <h2><ShieldCheck size={18} /> Approval Queue</h2>
          <p>2 generated contracts pending human approval. No output is finalized silently.</p>
        </article>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);

