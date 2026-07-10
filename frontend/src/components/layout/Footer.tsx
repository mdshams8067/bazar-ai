export function Footer() {
  return (
    <footer className="mt-16 border-t border-line bg-ink text-paper-warm">
      <div className="mx-auto grid max-w-6xl gap-8 px-4 py-10 sm:grid-cols-3">
        <div>
          <p className="font-heading text-lg font-extrabold text-white">Bazar AI</p>
          <p className="mt-2 max-w-xs text-sm text-paper-warm/70">
            Grocery, sorted by what you're cooking. Real prices, real stock, real substitutions —
            no guesswork.
          </p>
        </div>
        <div className="text-sm text-paper-warm/80">
          <p className="font-heading mb-2 font-bold text-white">Delivery</p>
          <p>Same-day delivery across Dhaka.</p>
          <p>Order before 6pm for next-morning slots.</p>
        </div>
        <div className="text-sm text-paper-warm/80">
          <p className="font-heading mb-2 font-bold text-white">Payments</p>
          <p>bKash, Nagad, cards, and net banking via SSLCommerz, or cash on delivery.</p>
        </div>
      </div>
      <div className="border-t border-white/10 px-4 py-4 text-center text-xs text-paper-warm/50">
        © {new Date().getFullYear()} Bazar AI. Inspired by Shwapno, built independently.
      </div>
    </footer>
  )
}
