import { Outlet } from 'react-router-dom'
import { ChatWidget } from '../chat/ChatWidget'
import { ColdStartBanner } from './ColdStartBanner'
import { Footer } from './Footer'
import { Header } from './Header'

export function Layout() {
  return (
    <div className="flex min-h-screen flex-col">
      <ColdStartBanner />
      <Header />
      <main className="flex-1">
        <Outlet />
      </main>
      <Footer />
      <ChatWidget />
    </div>
  )
}
