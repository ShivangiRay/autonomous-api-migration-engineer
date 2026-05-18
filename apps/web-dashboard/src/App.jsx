import React, { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  ArrowRight,
  Bot,
  CheckCircle2,
  CircleDot,
  Code2,
  FileCheck2,
  GitCompare,
  Layers3,
  MessagesSquare,
  Network,
  Play,
  RadioTower,
  ShieldCheck,
  Sparkles,
  Workflow,
  XCircle
} from "lucide-react";
import "./styles.css";

const endpoints = [
  {
    id: "GET /users",
    method: "GET",
    path: "/users",
    target: "keep_rest",
    confidence: 0.91,
    score: 92,
    status: "retained",
    reason: "Collection-style read endpoint remains efficient and externally friendly as REST.",
    evidence: "OpenAPI pagination parameters: page, pageSize",
    diff: "- REST GET /users?page=1&pageSize=25\n+ Keep REST collection endpoint\n+ Add pagination contract notes"
  },
  {
    id: "POST /users",
    method: "POST",
    path: "/users",
    target: "migrate_grpc",
    confidence: 0.86,
    score: 84,
    status: "recommended",
    reason: "Typed request/response operation benefits from strongly versioned gRPC contracts.",
    evidence: "OpenAPI request body: CreateUserRequest, response: User",
    diff:
      "- REST POST /users\n- body: { email }\n+ rpc CreateUser(CreateUserRequest) returns (CreateUserResponse)\n+ message CreateUserRequest { string email = 1; }"
  },
  {
    id: "GET /users/{userId}",
    method: "GET",
    path: "/users/{userId}",
    target: "migrate_grpc",
    confidence: 0.86,
    score: 88,
    status: "recommended",
    reason: "Point lookup maps cleanly to unary gRPC and stable User response contracts.",
    evidence: "OpenAPI response schema: User",
    diff:
      "- REST GET /users/{userId}\n+ rpc GetUser(GetUserRequest) returns (GetUserResponse)\n+ message GetUserRequest { string user_id = 1; }"
  },
  {
    id: "PATCH /users/{userId}",
    method: "PATCH",
    path: "/users/{userId}",
    target: "convert_event",
    confidence: 0.86,
    score: 76,
    status: "recommended",
    reason: "User status transitions should publish an asynchronous fact for downstream consumers.",
    evidence: "operationId: updateUserStatus",
    transport: "Kafka",
    diff:
      "- REST PATCH /users/{userId}\n+ channel users.updateUserStatus.v1\n+ event UserStatusUpdatedEvent\n+ recommended transport: Kafka"
  },
  {
    id: "PUT /admin/users/{userId}/roles",
    method: "PUT",
    path: "/admin/users/{userId}/roles",
    target: "split_context",
    confidence: 0.72,
    score: 61,
    status: "needs_context",
    reason: "Admin role management crosses a bounded context; split ownership before protocol migration.",
    evidence: "Path prefix: /admin",
    diff: "- REST PUT /admin/users/{userId}/roles\n+ Split AdminRoleService boundary first\n+ Re-run planner after context split"
  }
];

const targetLabels = {
  keep_rest: "Keep REST",
  migrate_grpc: "gRPC",
  convert_event: "Event",
  split_context: "Split context"
};

const targetClasses = {
  keep_rest: "rest",
  migrate_grpc: "grpc",
  convert_event: "event",
  split_context: "split"
};

function App() {
  const [selectedId, setSelectedId] = useState("POST /users");
  const [proposals, setProposals] = useState({});
  const [commentText, setCommentText] = useState("Add idempotency key and validation notes");
  const [activity, setActivity] = useState([
    "Scanner parsed 5 OpenAPI endpoints.",
    "Planner found 2 gRPC candidates and 1 event candidate.",
    "Verifier flagged idempotency and pagination review points."
  ]);

  const selected = endpoints.find((endpoint) => endpoint.id === selectedId);
  const proposal = proposals[selectedId];

  const metrics = useMemo(() => {
    const grpc = endpoints.filter((endpoint) => endpoint.target === "migrate_grpc").length;
    const events = endpoints.filter((endpoint) => endpoint.target === "convert_event").length;
    const rest = endpoints.filter((endpoint) => endpoint.target === "keep_rest").length;
    const risks = endpoints.filter((endpoint) => endpoint.score < 80).length;
    const readiness = Math.round(endpoints.reduce((sum, endpoint) => sum + endpoint.score, 0) / endpoints.length);
    return [
      ["Endpoints", endpoints.length, "blue"],
      ["gRPC candidates", grpc, "violet"],
      ["Event candidates", events, "green"],
      ["REST retained", rest, "amber"],
      ["Risk flags", risks, "red"],
      ["Readiness", `${readiness}%`, "cyan"]
    ];
  }, []);

  const createProposal = () => {
    if (!["migrate_grpc", "convert_event"].includes(selected.target)) {
      pushActivity(`${selected.id} is not actionable yet. Planner recommends ${targetLabels[selected.target]}.`);
      return;
    }
    const next = {
      status: "needs_review",
      comments: [],
      resolved: false,
      approved: false,
      implemented: false
    };
    setProposals({ ...proposals, [selectedId]: next });
    pushActivity(`Generated ${targetLabels[selected.target]} proposal for ${selected.id}.`);
  };

  const addComment = () => {
    if (!proposal || !commentText.trim()) return;
    setProposals({
      ...proposals,
      [selectedId]: {
        ...proposal,
        status: "changes_requested",
        comments: [...proposal.comments, commentText.trim()],
        resolved: false,
        approved: false
      }
    });
    pushActivity(`Developer commented on ${selected.id}: "${commentText.trim()}"`);
  };

  const resolveComments = () => {
    if (!proposal) return;
    setProposals({
      ...proposals,
      [selectedId]: { ...proposal, status: "needs_review", resolved: true }
    });
    pushActivity(`Resolved review comments for ${selected.id} and updated the proposed contract.`);
  };

  const approveProposal = () => {
    if (!proposal || (proposal.comments.length > 0 && !proposal.resolved)) return;
    setProposals({
      ...proposals,
      [selectedId]: { ...proposal, status: "approved", approved: true }
    });
    pushActivity(`Approved proposal for ${selected.id}.`);
  };

  const implementProposal = () => {
    if (!proposal?.approved || selected.target !== "migrate_grpc") return;
    setProposals({
      ...proposals,
      [selectedId]: { ...proposal, status: "implemented", implemented: true }
    });
    pushActivity(`Generated gRPC proto, service scaffold, adapter, and mapping test for ${selected.id}.`);
  };

  const pushActivity = (message) => {
    setActivity((current) => [message, ...current].slice(0, 6));
  };

  return (
    <main className="shell">
      <header className="hero">
        <div>
          <p className="eyebrow"><Sparkles size={14} /> Autonomous API Migration Engineer</p>
          <h1>REST migration control room</h1>
          <p className="lede">
            Review endpoint evidence, generate gRPC/event proposals, resolve comments, and approve migration work exactly like the CLI flow.
          </p>
        </div>
        <div className="heroPanel">
          <span>Demo service</span>
          <strong>User Management API</strong>
          <small>OpenAPI v3 fixture loaded</small>
        </div>
      </header>

      <section className="metrics">
        {metrics.map(([label, value, tone]) => (
          <article className={`metric ${tone}`} key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </article>
        ))}
      </section>

      <section className="workspace">
        <aside className="endpointPanel">
          <div className="panelTitle">
            <Layers3 size={18} />
            <h2>Endpoint Inventory</h2>
          </div>
          <div className="endpointList">
            {endpoints.map((endpoint) => (
              <button
                className={`endpointRow ${selectedId === endpoint.id ? "active" : ""}`}
                key={endpoint.id}
                onClick={() => setSelectedId(endpoint.id)}
              >
                <span className={`method ${endpoint.method.toLowerCase()}`}>{endpoint.method}</span>
                <span className="endpointPath">{endpoint.path}</span>
                <span className={`pill ${targetClasses[endpoint.target]}`}>{targetLabels[endpoint.target]}</span>
              </button>
            ))}
          </div>
        </aside>

        <section className="detailPanel">
          <div className="detailHeader">
            <div>
              <span className={`method ${selected.method.toLowerCase()}`}>{selected.method}</span>
              <h2>{selected.path}</h2>
              <p>{selected.reason}</p>
            </div>
            <div className="scoreRing">
              <span>{selected.score}</span>
              <small>compat</small>
            </div>
          </div>

          <div className="tabs">
            <article>
              <h3><Bot size={16} /> Explainability</h3>
              <p>{selected.evidence}</p>
              <div className="confidence"><span style={{ width: `${selected.confidence * 100}%` }} /></div>
              <small>{Math.round(selected.confidence * 100)}% recommendation confidence</small>
            </article>
            <article>
              <h3><GitCompare size={16} /> Contract Diff</h3>
              <pre>{selected.diff}</pre>
            </article>
          </div>

          <div className="approvalFlow">
            <h3><ShieldCheck size={17} /> Human Approval Queue</h3>
            <div className="flowSteps">
              <Step icon={<Play size={16} />} label="Proposal" done={Boolean(proposal)} active={!proposal} />
              <Step icon={<MessagesSquare size={16} />} label="Comments" done={proposal?.comments.length > 0} active={proposal?.status === "changes_requested"} />
              <Step icon={<FileCheck2 size={16} />} label="Approved" done={proposal?.approved} active={proposal?.status === "needs_review"} />
              <Step icon={<Code2 size={16} />} label="Implemented" done={proposal?.implemented} active={proposal?.approved && !proposal?.implemented} />
            </div>

            <div className="actions">
              <button onClick={createProposal}>
                <Sparkles size={16} /> Generate proposal
              </button>
              <button onClick={addComment} disabled={!proposal}>
                <MessagesSquare size={16} /> Add comment
              </button>
              <button onClick={resolveComments} disabled={!proposal || proposal.comments.length === 0 || proposal.resolved}>
                <CheckCircle2 size={16} /> Resolve comments
              </button>
              <button onClick={approveProposal} disabled={!proposal || (proposal.comments.length > 0 && !proposal.resolved)}>
                <ShieldCheck size={16} /> Approve
              </button>
              <button onClick={implementProposal} disabled={!proposal?.approved || selected.target !== "migrate_grpc"}>
                <Code2 size={16} /> Implement gRPC
              </button>
            </div>

            <label className="commentBox">
              Developer comment
              <input value={commentText} onChange={(event) => setCommentText(event.target.value)} />
            </label>

            <ProposalPreview endpoint={selected} proposal={proposal} />
          </div>
        </section>
      </section>

      <section className="lowerGrid">
        <article className="graphPanel">
          <h2><Network size={18} /> Migration Graph</h2>
          <div className="graphLine">
            <Node label="OpenAPI scan" icon={<Activity size={16} />} />
            <ArrowRight size={18} />
            <Node label="Planner DAG" icon={<Workflow size={16} />} />
            <ArrowRight size={18} />
            <Node label="Proposal review" icon={<ShieldCheck size={16} />} />
            <ArrowRight size={18} />
            <Node label="Generated code" icon={<Code2 size={16} />} />
          </div>
        </article>
        <article className="activityPanel">
          <h2><CircleDot size={18} /> Agent Activity</h2>
          <ul>
            {activity.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </article>
      </section>
    </main>
  );
}

function Step({ icon, label, done, active }) {
  return (
    <div className={`step ${done ? "done" : ""} ${active ? "activeStep" : ""}`}>
      {done ? <CheckCircle2 size={16} /> : icon}
      <span>{label}</span>
    </div>
  );
}

function Node({ icon, label }) {
  return <div className="graphNode">{icon}<span>{label}</span></div>;
}

function ProposalPreview({ endpoint, proposal }) {
  if (!proposal) {
    return (
      <div className="emptyState">
        <XCircle size={18} />
        No proposal generated for this endpoint yet.
      </div>
    );
  }

  if (endpoint.target === "convert_event") {
    return (
      <div className="proposalPreview eventPreview">
        <h4><RadioTower size={16} /> Event proposal</h4>
        <p><strong>Recommended transport:</strong> Kafka</p>
        <p>Durable user status events need replay, fan-out, and audit-friendly ordering for downstream consumers.</p>
      </div>
    );
  }

  return (
    <div className="proposalPreview">
      <h4><Code2 size={16} /> gRPC proposal</h4>
      <pre>{endpoint.id === "POST /users"
        ? "service UserManagementGrpc {\n  rpc CreateUser(CreateUserRequest) returns (CreateUserResponse);\n}\n\nmessage CreateUserRequest {\n  string email = 1;\n  string idempotency_key = 2;\n}"
        : "service UserManagementGrpc {\n  rpc GetUser(GetUserRequest) returns (GetUserResponse);\n}\n\nmessage GetUserRequest {\n  string user_id = 1;\n}"}</pre>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
