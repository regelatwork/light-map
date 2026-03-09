export const Dashboard = () => {
  return (
    <div className="flex h-screen bg-gray-100">
      <aside className="w-64 bg-white shadow-md">
        <div className="border-b p-4 font-bold text-black">Light Map Control</div>
        <nav className="p-4 text-black">Sidebar Content</nav>
      </aside>
      <main className="flex-1 overflow-auto p-8">
        <h2 className="mb-4 text-xl font-semibold text-black">Schematic View Placeholder</h2>
        <div className="flex h-96 items-center justify-center border-2 border-dashed border-gray-300 bg-white text-black">
          [Interactive Canvas Will Go Here]
        </div>
      </main>
    </div>
  );
};
