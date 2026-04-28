import Image from "next/image";
import { useState, useMemo } from "react";

const SourceCard = ({ source }: { source: { name: string; url: string } }) => {
  const [imageSrc, setImageSrc] = useState(`https://www.google.com/s2/favicons?domain=${source.url}&sz=128`);

  const handleImageError = () => {
    setImageSrc("/img/globe.svg");
  };
  
  // Extract and format the domain from the URL
  const formattedUrl = useMemo(() => {
    try {
      const urlObj = new URL(source.url);
      return urlObj.hostname.replace(/^www\./, '');
    } catch (e) {
      // If URL parsing fails, use the original URL but trim it
      return source.url.length > 50 ? source.url.substring(0, 50) + '...' : source.url;
    }
  }, [source.url]);

  return (
    <div className="apple-panel flex h-[88px] w-full items-center gap-3 rounded-[24px] border-white/8 px-4 py-3 shadow-[0_14px_36px_rgba(0,0,0,0.24)] transition-colors duration-200 md:w-auto hover:border-white/16 hover:bg-white/[0.06]">
      
        <img
          src={imageSrc}
          alt={source.url}
          className="rounded-2xl bg-white/5 p-1.5"
          width={44}
          height={44}
          onError={handleImageError}  // Update src on error
        />
      
      <div className="flex max-w-[192px] flex-col justify-center gap-[7px]">
        <h6 className="line-clamp-2 text-sm font-medium leading-[normal] text-white/86">
          {source.name}
        </h6>
        <a
          target="_blank"
          rel="noopener noreferrer"
          href={source.url}
          className="truncate text-sm font-light text-white/40 transition-colors hover:text-white/78"
          title={source.url}
        >
          {formattedUrl}
        </a>
      </div>
    </div>
  );
};

export default SourceCard;
