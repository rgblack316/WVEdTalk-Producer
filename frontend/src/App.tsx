import { Routes, Route } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import Home from "@/pages/Home";
import Archive from "@/pages/Archive";
import BriefingPage from "@/pages/BriefingPage";
import StoryDetail from "@/pages/StoryDetail";
import Candidates from "@/pages/Candidates";

// One <Route> per page in src/pages; BrowserRouter already wraps this in main.tsx.
export default function App() {
  return (
    <>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/archive" element={<Archive />} />
        <Route path="/candidates" element={<Candidates />} />
        <Route path="/briefings/:date" element={<BriefingPage />} />
        <Route path="/briefings/:date/stories/:storyId" element={<StoryDetail />} />
      </Routes>
      <Toaster />
    </>
  );
}
