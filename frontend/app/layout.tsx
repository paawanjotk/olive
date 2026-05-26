import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Yuno',
  description: 'Yuno AI Chat — powered by Claude and Gemini',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <body>{children}</body>
    </html>
  )
}
