import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2, UserPlus } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { z } from "zod";
import { ErrorNote, PageFade } from "../../components/ui";
import { toApiError } from "../../lib/api";
import { AuthLayout, AuthLink } from "./AuthLayout";
import { useAuth } from "./AuthContext";

const schema = z
  .object({
    name: z.string().trim().min(1, "Name is required").max(120),
    email: z.string().min(1, "Email is required").email("That does not look like an email"),
    // Matches the backend's minimum, so the server never rejects what the form accepted.
    password: z.string().min(8, "Use at least 8 characters").max(128),
    confirm: z.string(),
  })
  .refine((values) => values.password === values.confirm, {
    message: "Passwords do not match",
    path: ["confirm"],
  });

type Values = z.infer<typeof schema>;

export default function RegisterPage() {
  const { register: signUp } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", email: "", password: "", confirm: "" },
  });

  const onSubmit = async (values: Values) => {
    setError(null);
    try {
      await signUp(values.name, values.email, values.password);
      navigate("/groups", { replace: true });
    } catch (caught) {
      setError(toApiError(caught).message);
    }
  };

  return (
    <PageFade>
      <AuthLayout
        title="Create your account"
        subtitle="Start splitting expenses in about a minute."
        footer={<>Already have one? <AuthLink to="/login">Sign in</AuthLink></>}
      >
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div>
            <label htmlFor="name" className="label mb-1.5 block">
              Name
            </label>
            <input
              id="name"
              autoComplete="name"
              placeholder="Priya Sharma"
              className="input"
              {...register("name")}
            />
            {errors.name ? <p className="mt-1.5 text-xs text-debit">{errors.name.message}</p> : null}
          </div>

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
              {...register("email")}
            />
            {errors.email ? (
              <p className="mt-1.5 text-xs text-debit">{errors.email.message}</p>
            ) : null}
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="password" className="label mb-1.5 block">
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="new-password"
                placeholder="••••••••"
                className="input"
                {...register("password")}
              />
              {errors.password ? (
                <p className="mt-1.5 text-xs text-debit">{errors.password.message}</p>
              ) : null}
            </div>
            <div>
              <label htmlFor="confirm" className="label mb-1.5 block">
                Confirm
              </label>
              <input
                id="confirm"
                type="password"
                autoComplete="new-password"
                placeholder="••••••••"
                className="input"
                {...register("confirm")}
              />
              {errors.confirm ? (
                <p className="mt-1.5 text-xs text-debit">{errors.confirm.message}</p>
              ) : null}
            </div>
          </div>

          <ErrorNote message={error} />

          <button type="submit" disabled={isSubmitting} className="btn-primary w-full">
            {isSubmitting ? (
              <>
                <Loader2 size={16} className="animate-spin" /> Creating account…
              </>
            ) : (
              <>
                <UserPlus size={16} /> Create account
              </>
            )}
          </button>
        </form>
      </AuthLayout>
    </PageFade>
  );
}
