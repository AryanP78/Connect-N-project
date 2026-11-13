import { NavLink, Route, Routes } from 'react-router-dom'
import Home from './pages/Home.jsx'
import Game from './pages/Game.jsx'
import Arena from './pages/Arena.jsx'
import Analytics from './pages/Analytics.jsx'
import Insights from './pages/Insights.jsx'

const NAV = [
  ['/', 'Home'], ['/play', 'Play'], ['/arena', 'AI Arena'], ['/analytics', 'Analytics'], ['/insights', 'AI Insights'],
]

function Logo() {
  return (
    <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="7" fill="#14213d" />
      <circle cx="10" cy="10" r="4.2" fill="#e66767" /><circle cx="22" cy="10" r="4.2" fill="#eda100" />
      <circle cx="10" cy="22" r="4.2" fill="#eda100" /><circle cx="22" cy="22" r="4.2" fill="#e66767" />
    </svg>
  )
}

export default function App() {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="sticky top-0 z-20 backdrop-blur bg-page/80 border-b border-line">
        <div className="max-w-7xl mx-auto px-4 h-14 flex items-center gap-4">
          <NavLink to="/" className="flex items-center gap-2 font-semibold tracking-tight shrink-0">
            <Logo /> <span>Connect-N <span className="text-accent">AI</span></span>
          </NavLink>
          <nav className="flex gap-1 overflow-x-auto ml-auto sm:ml-4" aria-label="Main">
            {NAV.map(([to, label]) => (
              <NavLink key={to} to={to} end={to === '/'}
                className={({ isActive }) => `px-3 py-1.5 rounded-lg text-sm whitespace-nowrap transition-colors ${isActive ? 'bg-raised text-ink' : 'text-ink2 hover:text-ink'}`}>
                {label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 py-6 sm:py-8">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/play" element={<Game />} />
          <Route path="/arena" element={<Arena />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/insights" element={<Insights />} />
          <Route path="*" element={<Home />} />
        </Routes>
      </main>
      <footer className="border-t border-line text-xs text-muted py-4 text-center">
        Connect-N AI - one shared game engine, five AI agents, one benchmarking framework, one application.
      </footer>
    </div>
  )
}
