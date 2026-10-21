import React from 'react';
import Layout from '@theme/Layout';
import Link from '@docusaurus/Link';
import CodeBlock from '@theme/CodeBlock';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';

const sample = `import asyncio
import os
from gramflux import Client, Session, filters

async def main():
    client = Client(
        Session.open("account"),
        api_id=int(os.environ["GRAMFLUX_API_ID"]),
        api_hash=os.environ["GRAMFLUX_API_HASH"],
    )

    @client.on_message(filters.incoming & filters.text)
    async def on_message(event):
        await event.reply("Hello from GramFlux")

    async with client:
        await client.run_until_disconnected()

asyncio.run(main())`;

const journeys = [
  ['01', 'A deliberate first connection', 'Install, authorize a named session, and send your first message.', '/docs/getting-started/quickstart', 'Start building'],
  ['02', 'Sessions that fit your workflow', 'Create, reopen, or keep a session in memory. Resume unfinished logins.', '/docs/guides/authentication', 'Understand login'],
  ['03', 'React to what matters', 'Compose filters and handle messages, callbacks, inline queries and raw updates.', '/docs/guides/events', 'Explore events'],
  ['04', 'Take the native route', 'Call the official schema directly with typed keyword arguments and native objects.', '/docs/guides/async-api', 'Use the raw API'],
  ['05', 'Move files with bounds', 'Stream chunks, report progress, and choose explicit transfer concurrency.', '/docs/guides/files', 'Work with files'],
  ['06', 'Know your guarantees', 'Understand deadlines, cancellation, update recovery and uncertain outcomes.', '/docs/guides/errors', 'Design for failure'],
];

export default function Home() {
  const {siteConfig} = useDocusaurusContext();
  const {gramfluxVersion, rawMethodCount, updateConstructorCount} = siteConfig.customFields;
  return (
    <Layout title="Python, connected to Telegram" description="The official GramFlux documentation. Build with an independent asyncio MTProto runtime, explicit sessions, typed APIs and predictable failures.">
      <main className="landing">
        <div className="landing__hero">
          <section className="landing__intro" aria-labelledby="hero-title">
            <Link className="release-pill" to="/docs/releases/0.5.0a2"><span aria-hidden="true"/> Engineering alpha <span className="release-pill__version">{gramfluxVersion}</span></Link>
            <p className="eyebrow">THE PYTHON TELEGRAM TOOLKIT</p>
            <h1 id="hero-title">One client.<br/>Every layer.</h1>
            <p className="landing__description">Build with a clear async API. Reach the official schema when you need more. Stay in control of sessions, updates and failures.</p>
            <div className="landing__actions">
              <Link className="button button--primary button--lg" to="/docs/getting-started/quickstart">Get started <span aria-hidden="true">↗</span></Link>
              <Link className="landing__text-link" to="/docs/reference/client">Explore the API <span aria-hidden="true">→</span></Link>
            </div>
            <div className="landing__facts" aria-label="Schema and compatibility facts">
              <span><strong>3.11+</strong> Python</span>
              <span><strong>{rawMethodCount}</strong> raw functions</span>
              <span><strong>{updateConstructorCount}</strong> Update types</span>
            </div>
          </section>
          <section className="code-window" aria-label="An authorized client receiving messages">
            <div className="code-window__bar"><span className="code-window__dots" aria-hidden="true"><i/><i/><i/></span><span>client.py</span><span className="code-window__label">ASYNC / PYTHON</span></div>
            <CodeBlock language="python" showLineNumbers>{sample}</CodeBlock>
            <div className="code-window__note"><span aria-hidden="true">↳</span> Reuses an authorized session. <Link to="/docs/guides/authentication">Create one first.</Link></div>
          </section>
        </div>
        <section className="protocol-strip" aria-label="Independent native runtime">
          <div><span className="eyebrow">INDEPENDENT BY ARCHITECTURE</span><p>One native execution path.</p></div>
          <ol><li>Client</li><li>Typed TL</li><li>MTProto 2.0</li><li>Async TCP</li></ol>
          <Link to="/docs/design/architecture">See how it works <span aria-hidden="true">↗</span></Link>
        </section>
        <section className="journeys" aria-labelledby="journeys-title">
          <div className="section-heading"><div><p className="eyebrow">FROM FIRST CALL TO FULL CONTROL</p><h2 id="journeys-title">Find your next step.</h2></div><p>Practical guides. Exact signatures.<br/>Honest boundaries.</p></div>
          <div className="journeys__grid">{journeys.map(([number, title, description, to, label]) => (
            <Link className="journey" key={number} to={to}><span className="journey__number">{number}</span><h3>{title}</h3><p>{description}</p><span className="journey__link">{label} <span aria-hidden="true">↗</span></span></Link>
          ))}</div>
        </section>
        <section className="status-note" aria-labelledby="status-title"><div className="status-note__badge">A NOTE ON STATUS</div><div><h2 id="status-title">Evidence before confidence.</h2><p>GramFlux is an engineering alpha. Schema coverage and controlled tests do not certify every workflow against a live account. Read the compatibility matrix before adopting it.</p><Link to="/docs/design/compatibility">View capabilities and limitations <span aria-hidden="true">→</span></Link></div></section>
      </main>
    </Layout>
  );
}
