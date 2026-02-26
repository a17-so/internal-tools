import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';

export async function POST(request: Request) {
    try {
        const cookieStore = await cookies();
        const accessToken = cookieStore.get('tiktok_access_token')?.value;
        const openId = cookieStore.get('tiktok_open_id')?.value;

        if (!accessToken || !openId) {
            return NextResponse.json({ error: 'Unauthorized. Please log in with TikTok first.' }, { status: 401 });
        }

        const formData = await request.formData();
        const videoFile = formData.get('video') as File | null;
        const title = formData.get('title') as string | null;

        if (!videoFile) {
            return NextResponse.json({ error: 'No video file provided' }, { status: 400 });
        }

        const videoSize = videoFile.size;

        // 1. Initialize Upload
        const initResponse = await fetch('https://open.tiktokapis.com/v2/post/publish/inbox/video/init/', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${accessToken}`,
                'Content-Type': 'application/json; charset=UTF-8',
            },
            body: JSON.stringify({
                source_info: {
                    source: 'FILE_UPLOAD',
                    video_size: videoSize,
                    chunk_size: videoSize,
                    total_chunk_count: 1
                },
                ...(title ? { post_info: { title } } : {})
            })
        });

        const initData = await initResponse.json();

        if (!initResponse.ok || (initData.error?.code && initData.error.code !== 'ok')) {
            console.error('TikTok Init Error:', initData);
            return NextResponse.json({ error: initData.error?.message || 'Failed to initialize upload' }, { status: 400 });
        }

        const uploadUrl = initData.data?.upload_url;
        if (!uploadUrl) {
            return NextResponse.json({ error: 'No upload URL returned from TikTok' }, { status: 500 });
        }

        // 2. Upload Video to the provided URL
        const videoArrayBuffer = await videoFile.arrayBuffer();
        const videoBuffer = Buffer.from(videoArrayBuffer);

        const uploadResponse = await fetch(uploadUrl, {
            method: 'PUT',
            headers: {
                'Content-Range': `bytes 0-${videoSize - 1}/${videoSize}`,
                'Content-Type': videoFile.type || 'video/mp4',
                'Content-Length': videoSize.toString(),
            },
            body: videoBuffer
        });

        if (!uploadResponse.ok) {
            const uploadErrorText = await uploadResponse.text();
            console.error('TikTok Upload Error:', uploadErrorText);
            return NextResponse.json({ error: 'Failed to upload video chunk to TikTok' }, { status: 500 });
        }

        return NextResponse.json({ success: true, message: 'Video successfully uploaded to TikTok drafts' });

    } catch (error: any) {
        console.error('Upload handling error:', error);
        return NextResponse.json({ error: error.message || 'Internal Server Error' }, { status: 500 });
    }
}
