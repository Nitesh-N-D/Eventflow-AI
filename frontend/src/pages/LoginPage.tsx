import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      navigate("/dashboard");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Invalid email or password");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-bg grid-bg flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-accent/20 border border-accent/40 rounded-2xl flex items-center justify-center text-3xl mx-auto mb-4">
            ⚡
          </div>
          <h1 className="text-2xl font-bold">EventFlow AI</h1>
          <p className="text-muted text-sm mt-1">Smart City Traffic Command Center</p>
        </div>

        <div className="glass-card p-8">
          <h2 className="text-lg font-bold mb-1">Sign In</h2>
          <p className="text-muted text-sm mb-6">Access the traffic management dashboard</p>

          {error && (
            <div className="bg-bad/10 border border-bad/30 text-bad text-sm rounded-lg px-4 py-3 mb-4">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="label">Email</label>
              <input
                type="email" value={email}
                onChange={e => setEmail(e.target.value)}
                className="input-field" placeholder="officer@trafficpolice.gov.in"
                required
              />
            </div>
            <div>
              <label className="label">Password</label>
              <input
                type="password" value={password}
                onChange={e => setPassword(e.target.value)}
                className="input-field" placeholder="••••••••"
                required
              />
            </div>
            <button type="submit" className="btn-primary w-full" disabled={loading}>
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Signing in...
                </span>
              ) : "Sign In"}
            </button>
          </form>

          <p className="text-center text-sm text-muted mt-6">
            Don't have an account?{" "}
            <Link to="/register" className="text-accent hover:underline">Register</Link>
          </p>
        </div>

        <p className="text-center text-xs text-muted mt-6">
          Built on real ASTRAM Bengaluru traffic incident data
        </p>
      </div>
    </div>
  );
}
