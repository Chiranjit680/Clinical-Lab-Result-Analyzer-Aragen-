import { useEffect, useState } from 'react'
import logo from './assets/lab-record-logo.png'
import './navbar.css'

const NAV_ITEMS = [
  { id: 'home', label: 'Home' },
  { id: 'analyze', label: 'Analyze' },
  { id: 'consultation', label: 'Consultation' },
  { id: 'about', label: 'About' },
]

/**
 * Sticky gradient navbar. Every link stays on the bar at all widths — the row
 * wraps beneath the logo on narrow screens rather than collapsing behind a menu.
 *
 * Uncontrolled by default; pass `active` to drive the highlighted item from a
 * parent. `onNavigate(id)` fires on every selection, and the matching
 * `#<id>` section is scrolled into view when one exists on the page.
 */
export default function Navbar({ items = NAV_ITEMS, active, onNavigate }) {
  const [internalActive, setInternalActive] = useState(items[0]?.id)
  const [scrolled, setScrolled] = useState(false)

  const selected = active ?? internalActive

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  function handleSelect(event, id) {
    event.preventDefault()
    setInternalActive(id)
    onNavigate?.(id)

    const target = document.getElementById(id)
    if (!target) return
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    target.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' })
  }

  return (
    <header className={`navbar${scrolled ? ' is-scrolled' : ''}`}>
      <div className="navbar__inner">
        <a
          className="navbar__brand"
          href={`#${items[0]?.id ?? 'home'}`}
          onClick={(event) => handleSelect(event, items[0]?.id ?? 'home')}
        >
          <span className="navbar__logo">
            <img src={logo} alt="LabRecord Analyzer" />
          </span>
        </a>

        <nav className="navbar__nav" aria-label="Primary">
          <ul className="navbar__links">
            {items.map((item) => (
              <li key={item.id}>
                <a
                  href={`#${item.id}`}
                  className={`navbar__link${selected === item.id ? ' is-active' : ''}`}
                  aria-current={selected === item.id ? 'page' : undefined}
                  onClick={(event) => handleSelect(event, item.id)}
                >
                  {item.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </header>
  )
}
