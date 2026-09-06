import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2, LogIn } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { z } from "zod";
import { ErrorNote, PageFade } from "../../components/ui";
import { toApiError } from "../../lib/api";
import { AuthLayout, AuthLink } from "./AuthLayout";
import { useAuth } from "./AuthContext";

const schema = z.object({
  email: z.string().min(1, "Email is required").email("That does not look like an email"),
  password: z.string().min(1, "Password is required"),
});

type Values = z.infer<typeof schema>;

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { email: "", password: "" } });

  const onSubmit = async (values: Values) => {
    setError(null);
    try {
      await login(values.email, values.password);
      navigate("/groups", { replace: true });
    } catch (caught) {
      setError(toApiError(caught).message);
    }
  };

  return (
    <PageFade>
      <AuthLayout
        title="Welcome back"
        subtitle="Sign in to see what you owe and who owes you."
        footer={<>New here? <AuthLink to="/register">Create an account</AuthLink></>}
      >
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div>
            <label htmlFor="email" className="label mb-1.5 block">
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              placeholder="you@example.com"
              className="input"
              aria-invalid={!!errors.email}
              {...register("email")}
            />
            {errors.email ? (
              <p className="mt-1.5 text-xs text-debit">{errors.email.message}</p>
            ) : null}
          </div>

          <div>
            <label htmlFor="password" className="label mb-1.5 block">
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              placeholder="••••••••"
              className="input"
              aria-invalid={!!errors.password}
              {...register("password")}
            />
            {errors.password ? (
              <p className="mt-1.5 text-xs text-debit">{errors.password.message}</p>
            ) : null}
          </div>

          <ErrorNote message={error} />

          <button type="submit" disabled={isSubmitting} className="btn-primary w-full">
            {isSubmitting ? (
              <>
                <Loader2 size={16} className="animate-spin" /> Signing in…
              </>
            ) : (
              <>
                <LogIn size={16} /> Sign in
              </>
            )}
          </button>
        </form>
      </AuthLayout>
    </PageFade>
  );
}
