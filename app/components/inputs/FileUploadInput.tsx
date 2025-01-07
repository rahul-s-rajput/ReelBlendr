import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Label } from '../../ui/label'
import { Button } from '../../ui/button'
import { X, GripVertical, Upload } from 'lucide-react'

interface FileUploadInputProps {
  label: string
  name: string
  value: File[]
  onChange: (name: string, value: File[]) => void
}

export default function FileUploadInput({ label, name, value, onChange }: FileUploadInputProps) {
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null)

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const validFiles = acceptedFiles.filter(file => file instanceof File)
    onChange(name, [...value, ...validFiles])
  }, [name, value, onChange])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({ 
    onDrop,
    accept: { 'video/*': [] },
    multiple: true,
    noClick: false,
    noKeyboard: false,
    preventDropOnDocument: true
  })

  const removeFile = (index: number) => {
    const newFiles = [...value]
    newFiles.splice(index, 1)
    onChange(name, newFiles)
  }

  const handleDragStart = (e: React.DragEvent<HTMLLIElement>, index: number) => {
    setDraggedIndex(index)
    e.dataTransfer.effectAllowed = 'move'
  }

  const handleDragOver = (e: React.DragEvent<HTMLLIElement>, index: number) => {
    e.preventDefault()
    if (draggedIndex === null || draggedIndex === index) return

    const newFiles = [...value]
    const [removed] = newFiles.splice(draggedIndex, 1)
    newFiles.splice(index, 0, removed)

    onChange(name, newFiles)
    setDraggedIndex(index)
  }

  const handleDragEnd = () => {
    setDraggedIndex(null)
  }

  return (
    <div className="space-y-4">
      <Label className="text-purple-400 flex items-center">
        {label}
        <span className="text-red-400 ml-1">*</span>
      </Label>
      <div
        {...getRootProps()}
        className={`mt-1 border-2 border-dashed rounded-lg p-6 text-center transition-all duration-300 ${
          isDragActive
            ? 'border-purple-400 bg-purple-900 bg-opacity-50'
            : 'border-purple-500 hover:border-purple-400 hover:bg-purple-900 hover:bg-opacity-25'
        }`}
      >
        <input {...getInputProps()} />
        <Upload className="mx-auto h-12 w-12 text-purple-400 mb-4" />
        {isDragActive ? (
          <p className="text-purple-400 font-medium">Drop the files here ...</p>
        ) : (
          <p className="text-purple-400 font-medium">
            Drag 'n' drop some files here, or click to select files
            <span className="text-red-400 ml-1">*</span>
          </p>
        )}
      </div>
      {Array.isArray(value) && value.length > 0 && (
        <ul className="mt-4 space-y-2 max-h-60 overflow-y-auto">
          {value.map((file, index) => (
            <li
              key={`${file.name}-${index}`}
              draggable
              onDragStart={(e) => handleDragStart(e, index)}
              onDragOver={(e) => handleDragOver(e, index)}
              onDragEnd={handleDragEnd}
              className={`flex items-center justify-between bg-gray-700 p-2 rounded cursor-move transition-all duration-300 ${
                index === draggedIndex ? 'opacity-50' : ''
              }`}
            >
              <div className="flex items-center">
                <span className="mr-2">
                  <GripVertical className="h-4 w-4 text-purple-400" />
                </span>
                <span className="text-white truncate max-w-xs">{file.name}</span>
              </div>
              <Button 
                type="button" 
                variant="ghost" 
                size="sm" 
                onClick={(e) => {
                  e.stopPropagation();
                  removeFile(index);
                }}
              >
                <X className="h-4 w-4 text-purple-400" />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

