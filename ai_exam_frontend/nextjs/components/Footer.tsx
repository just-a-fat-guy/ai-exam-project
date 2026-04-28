import React from 'react';
import Link from "next/link";
import Modal from './Settings/Modal';
import { ChatBoxSettings } from '@/types/data';

interface FooterProps {
  chatBoxSettings: ChatBoxSettings;
  setChatBoxSettings: React.Dispatch<React.SetStateAction<ChatBoxSettings>>;
}

const Footer: React.FC<FooterProps> = ({
  chatBoxSettings,
  setChatBoxSettings,
}) => {
  if (typeof window !== 'undefined') {
    const urlParams = new URLSearchParams(window.location.search);
    const urlDomains = urlParams.get("domains");
    if (urlDomains) {
      const domainArray = urlDomains.split(',').map(domain => ({
        value: domain.trim()
      }));
      localStorage.setItem('domainFilters', JSON.stringify(domainArray));
    }
  }

  return (
    <div className="apple-panel mx-auto flex w-full max-w-[1220px] flex-col items-center justify-between gap-4 rounded-[28px] border-white/8 px-5 py-5 sm:flex-row sm:px-6">
      <div className="order-2 text-center text-xs uppercase tracking-[0.2em] text-white/36 sm:order-1 sm:text-left">
        © {new Date().getFullYear()} GPT Researcher
      </div>

      <div className="order-1 sm:order-2">
        <Modal
          setChatBoxSettings={setChatBoxSettings}
          chatBoxSettings={chatBoxSettings}
        />
      </div>

      <div className="order-3 flex items-center gap-3">
        <Link
          href={"https://gptr.dev"}
          target="_blank"
          className="apple-button-ghost flex h-10 w-10 items-center justify-center rounded-full"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="h-5 w-5"
          >
            <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
            <polyline points="9 22 9 12 15 12 15 22" />
          </svg>
        </Link>
        <Link
          href={"https://github.com/assafelovic/gpt-researcher"}
          target="_blank"
          className="apple-button-ghost flex h-10 w-10 items-center justify-center rounded-full"
        >
          <img src={"/img/github.svg"} alt="github" width={18} height={18} className="invert" />
        </Link>
        <Link
          href={"https://discord.gg/QgZXvJAccX"}
          target="_blank"
          className="apple-button-ghost flex h-10 w-10 items-center justify-center rounded-full"
        >
          <img src={"/img/discord.svg"} alt="discord" width={18} height={18} className="invert" />
        </Link>
        <Link
          href={"https://hub.docker.com/r/gptresearcher/gpt-researcher"}
          target="_blank"
          className="apple-button-ghost flex h-10 w-10 items-center justify-center rounded-full"
        >
          <img src={"/img/docker.svg"} alt="docker" width={18} height={18} className="invert" />
        </Link>
      </div>
    </div>
  );
};

export default Footer;
