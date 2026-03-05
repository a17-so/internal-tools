'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';

export default function Uploader() {
    const [file, setFile] = useState<File | null>(null);
    const [title, setTitle] = useState('');
    const [isUploading, setIsUploading] = useState(false);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            setFile(e.target.files[0]);
        }
    };

    const handleUpload = async () => {
        if (!file) {
            toast.error('Please select a video file first');
            return;
        }

        setIsUploading(true);

        try {
            const formData = new FormData();
            formData.append('video', file);
            if (title.trim()) {
                formData.append('title', title.trim());
            }

            const res = await fetch('/api/upload', {
                method: 'POST',
                body: formData,
            });

            if (!res.ok) {
                const error = await res.json();
                throw new Error(error.error || 'Upload failed');
            }

            const data = await res.json();
            toast.success('Sent to TikTok! Check your TikTok INBOX to publish the draft.', { duration: 8000 });
            setFile(null); // Reset form
            setTitle('');
            // Reset the physical file input value to clear the UI
            const fileInput = document.getElementById('video-upload') as HTMLInputElement;
            if (fileInput) fileInput.value = '';
        } catch (err: any) {
            console.error('Upload Error:', err);
            toast.error(err.message || 'An error occurred during upload.');
        } finally {
            setIsUploading(false);
        }
    };

    return (
        <Card className="w-full max-w-md mx-auto">
            <CardHeader>
                <CardTitle>TikTok Draft Uploader</CardTitle>
                <CardDescription>
                    Upload an MP4 or WebM video directly to your TikTok account.
                    <br /><br />
                    <b>Note:</b> .mov files are not supported by the API. TikTok also combines title and caption into one field. After uploading, you will receive a notification in your <b>TikTok Inbox</b> to complete the draft!
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="space-y-2">
                    <Label htmlFor="video-title">Caption (Title)</Label>
                    <Input
                        id="video-title"
                        placeholder="Awesome video! #fyp"
                        value={title}
                        onChange={(e) => setTitle(e.target.value)}
                        disabled={isUploading}
                    />
                </div>
                <div className="space-y-2">
                    <Label htmlFor="video-upload">Select Video</Label>
                    <Input
                        id="video-upload"
                        type="file"
                        accept="video/mp4,video/webm"
                        onChange={handleFileChange}
                        disabled={isUploading}
                    />
                </div>
            </CardContent>
            <CardFooter>
                <Button
                    className="w-full"
                    onClick={handleUpload}
                    disabled={!file || isUploading}
                >
                    {isUploading ? 'Uploading...' : 'Upload to Drafts'}
                </Button>
            </CardFooter>
        </Card>
    );
}
