import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { authApi } from "../lib/api";

export default function RegisterPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "", full_name: "", role: "traffic_officer" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const update = (field: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm(f => ({ ...f, [field]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await authApi.register(form);
      navigate("/login");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-bg grid-bg flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-accent/20 border border-accent/40 rounded-2xl flex items-center justify-center text-3xl mx-auto mb-4">⚡</div>
          <h1 className="text-2xl font-bold">EventFlow AI</h1>
          <p className="text-muted text-sm mt-1">Create your account</p>
        </div>

        <div className="glass-card p-8">
          <h2 className="text-lg font-bold mb-6">Register</h2>

          {error && (
            <div className="bg-bad/10 border border-bad/30 text-bad text-sm rounded-lg px-4 py-3 mb-4">{error}</div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="label">Full Name</label>
              <input type="text" value={form.full_name} onChange={update("full_name")} className="input-field" placeholder="Ravi Kumar" required />
            </div>
            <div>
              <label className="label">Email</label>
              <input type="email" value={form.email} onChange={update("email")} className="input-field" placeholder="officer@trafficpolice.gov.in" required />
            </div>
            <div>
              <label className="label">Password</label>
              <input type="password" value={form.password} onChange={update("password")} className="input-field" placeholder="Min. 8 characters" required minLength={8} />
            </div>
            <div>
              <label className="label">Role</label>
              <select value={form.role} onChange={update("role")} className="input-field">
                <option value="traffic_officer">Traffic Officer</option>
                <option value="admin">Admin</option>
                <option value="public_user">Public User</option>
              </select>
            </div>
            <button type="submit" className="btn-primary w-full" disabled={loading}>
              {loading ? "Creating account..." : "Create Account"}
            </button>
          </form>

          <p className="text-center text-sm text-muted mt-6">
            Already have an account?{" "}
            <Link to="/login" className="text-accent hover:underline">Sign in</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
