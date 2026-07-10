import { createClient } from '@supabase/supabase-js'

// Safe to expose client-side by design — Supabase's security model is
// enforced by RLS policies on the database side, not by keeping this key
// secret (same idea as a Stripe publishable key vs. secret key).
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

export const supabase = createClient(supabaseUrl, supabaseAnonKey)
