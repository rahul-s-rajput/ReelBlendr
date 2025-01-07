interface TabButtonsProps {
  activeTab: string
  setActiveTab: (tab: string) => void
  isProcessing: boolean
}

export default function TabButtons({ activeTab, setActiveTab, isProcessing }: TabButtonsProps) {
  return (
    <div className="flex space-x-4 mb-6">
      {['video', 'audio', 'style'].map((tab) => (
        <button
          key={tab}
          onClick={() => setActiveTab(tab)}
          disabled={isProcessing}
          className={`px-4 py-2 rounded-lg transition-all duration-300 ${
            activeTab === tab
              ? 'bg-electric-blue text-white'
              : 'bg-gray-200 text-gray-600 hover:bg-gray-300'
          } ${isProcessing ? 'opacity-50 cursor-not-allowed' : ''}`}
        >
          {tab.charAt(0).toUpperCase() + tab.slice(1)}
        </button>
      ))}
    </div>
  )
} 