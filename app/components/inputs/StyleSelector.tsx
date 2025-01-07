import { Label } from '../../ui/label'
import { Button } from '../../ui/button'

interface StyleSelectorProps {
  label: string
  name: string
  value: string
  onChange: (name: string, value: string) => void
  options: string[]
}

export default function StyleSelector({ label, name, value, onChange, options }: StyleSelectorProps) {
  return (
    <div className="space-y-2">
      <Label className="text-gray-700 font-medium">{label}</Label>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {options.map((option) => (
          <Button
            key={option}
            variant={value === option ? 'default' : 'ghost'}
            onClick={() => onChange(name, option)}
            className={`h-24 flex flex-col items-center justify-center text-center p-2 ${
              value === option
                ? 'bg-electric-blue hover:bg-electric-blue-dark text-white'
                : 'bg-white hover:bg-gray-100 text-gray-800 border-gray-300'
            } transition-all duration-300`}
          >
            <span className="text-2xl mb-2">
              {option === 'Fast-paced' && '⚡'}
              {option === 'Smooth/Cinematic' && '🎬'}
              {option === 'Documentary' && '🎥'}
            </span>
            <span className="text-sm">{option}</span>
          </Button>
        ))}
      </div>
    </div>
  )
}

