import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../ui/select'
import { Label } from '../../ui/label'

interface DropdownInputProps {
  label: string
  name: string
  value: string
  onChange: (name: string, value: string) => void
  options: string[]
}

export default function DropdownInput({ label, name, value, onChange, options }: DropdownInputProps) {
  return (
    <div className="space-y-2">
      <Label htmlFor={name} className="text-gray-700 font-medium">{label}</Label>
      <Select value={value} onValueChange={(value) => onChange(name, value)}>
        <SelectTrigger className="w-full bg-white text-gray-800 border-gray-300 focus:border-electric-blue focus:ring focus:ring-electric-blue focus:ring-opacity-50 transition-all duration-300">
          <SelectValue placeholder="Select an option" />
        </SelectTrigger>
        <SelectContent className="bg-white text-gray-800 border-gray-300">
          {options.map((option) => (
            <SelectItem key={option} value={option} className="focus:bg-electric-blue focus:text-white cursor-pointer">
              {option}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

